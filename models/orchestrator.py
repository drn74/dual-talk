import asyncio
import time
import aiofiles

from models.agent import Agent
from models.critic import CriticAgent
from models.context import ContextManager
from utils.tools import perform_web_search

class Orchestrator:
    def __init__(self, agents: list[Agent], critic: CriticAgent, context: ContextManager, config: dict, log_file: str, memory_agent: any = None, session_id: str = None, semaphore: asyncio.Semaphore = None):
        self.agents = agents
        self.critic = critic
        self.context = context
        self.config = config
        self.log_file = log_file
        self.memory = memory_agent
        self.session_id = session_id
        self.semaphore = semaphore
        
        self.orchestrator_config = config.get("orchestrator", {})
        self.memory_config = config.get("memory", {})
        self.mode = self.orchestrator_config.get("mode", "round_robin")
        self.max_turns = self.orchestrator_config.get("max_turns", 20)
        self.inactivity_timeout_seconds = self.orchestrator_config.get("inactivity_timeout_seconds", 120)
        self.termination_on_completed = self.orchestrator_config.get("termination_on_completed", True)
        self.termination_on_max_turns = self.orchestrator_config.get("termination_on_max_turns", True)
        self.serper_api_key = config.get("serper_api_key", "")
        
        self.current_turn = 0
        self.last_activity_time = time.time()
        self.consecutive_stalls = 0
        self.active_agent_index = 0
        self.last_agent_name = None
        self.consecutive_turns = 0
        
        # Stats for summary
        self.agent_stats = {a.name: 0 for a in self.agents}
        self.critic_interventions = 0
        self.final_verdict = "INCOMPLETE"

    async def _write_log(self, role: str, content: str):
        async with aiofiles.open(self.log_file, mode='a', encoding='utf-8') as f:
            await f.write(f"**{role}**:\n{content}\n\n---\n\n")

    async def _select_next_agent(self, last_suggestion: str = "") -> Agent:
        """Selects the next agent based on the configured mode."""
        
        # Critic-directed selection
        if self.mode == "critic_directed" and last_suggestion:
            for i, agent in enumerate(self.agents):
                if agent.name in last_suggestion:
                    if self._can_agent_speak(agent):
                        self.active_agent_index = i
                        return agent
        
        # Weighted selection
        if self.mode == "weighted":
            import random
            possible_agents = [a for a in self.agents if self._can_agent_speak(a)]
            if not possible_agents: # Fallback if all agents are blocked (should not happen with N>=2)
                possible_agents = self.agents
            
            weights = [a.talk_ratio for a in possible_agents]
            chosen_agent = random.choices(possible_agents, weights=weights, k=1)[0]
            self.active_agent_index = self.agents.index(chosen_agent)
            return chosen_agent

        # Round Robin selection
        attempts = 0
        while attempts < len(self.agents):
            self.active_agent_index = (self.active_agent_index + 1) % len(self.agents)
            candidate = self.agents[self.active_agent_index]
            if self._can_agent_speak(candidate):
                return candidate
            attempts += 1
            
        return self.agents[self.active_agent_index] # Absolute fallback

    def _can_agent_speak(self, agent: Agent) -> bool:
        """Enforces turns constraints (max 2 consecutive for N >= 3)."""
        if len(self.agents) < 3:
            return True
        if agent.name == self.last_agent_name and self.consecutive_turns >= 2:
            return False
        return True

    async def _should_terminate(self, action: str) -> bool:
        """Checks if the session should terminate."""
        if self.termination_on_completed and action == "completed":
            self.final_verdict = "COMPLETED"
            return True
        if self.termination_on_max_turns and self.current_turn >= self.max_turns:
            self.final_verdict = "MAX_TURNS_REACHED"
            return True
        if time.time() - self.last_activity_time > self.inactivity_timeout_seconds:
            self.final_verdict = "TIMEOUT"
            return True
        if self.consecutive_stalls >= 3:
            self.final_verdict = "STALLED"
            return True
        return False

    async def _handle_action(self, agent: Agent, content: str, action: str) -> None:
        """Handles special actions like web search."""
        if action and action.startswith("search:"):
            query = action.split("search:", 1)[1]
            print(f"\n[Executing Web Search for: '{query}']")
            
            search_result = await asyncio.to_thread(perform_web_search, query, self.serper_api_key)
            
            # Print short snippet of result
            snippet = search_result[:100].replace('\n', ' ') + "..."
            print(f"[Web Result: {snippet}]")
            
            # Add to context as user role
            self.context.add_message("user", f"[System (Web Search Results)]: {search_result}")
            await self._write_log("System (Web Search)", f"Search results for '{query}':\n{search_result}")

    async def run(self) -> None:
        """Main loop of the conversation."""
        current_agent = self.agents[0]
        max_retries = 3
        last_suggestion = ""
        
        while True:
            self.current_turn += 1
            retry_count = 0
            content = ""
            action = None
            
            while retry_count < max_retries:
                # Agent generates response
                if self.semaphore:
                    async with self.semaphore:
                        content, action = await current_agent.generate_response(self.context)
                else:
                    content, action = await current_agent.generate_response(self.context)
                
                self.last_activity_time = time.time()
                
                if not content.strip():
                    retry_count += 1
                    print(f"\n[Warning] {current_agent.name} returned an empty response (Attempt {retry_count}/{max_retries}).")
                    if retry_count < max_retries:
                        await asyncio.sleep(5)
                    continue
                
                # Critic Evaluation
                if self.critic:
                    rejections = 0
                    max_rejections = self.config.get("critic", {}).get("max_rejections_per_turn", 2)
                    
                    while rejections < max_rejections:
                        print(f"\n[Critic] Evaluating {current_agent.name}'s response...")
                        if self.semaphore:
                            async with self.semaphore:
                                evaluation = await self.critic.evaluate(content)
                        else:
                            evaluation = await self.critic.evaluate(content)
                        
                        verdict = evaluation.get("verdict", "accept")
                        reason = evaluation.get("reason", "No reason provided")
                        suggestion = evaluation.get("suggestion", "")
                        
                        if verdict == "reject":
                            self.critic_interventions += 1
                            rejections += 1
                            print(f"[Critic] REJECT ({rejections}/{max_rejections}): {reason}")
                            
                            # Log the rejected attempt
                            await self._write_log(f"{current_agent.name} (Rejected)", f"{content}\n\n**Critic Reason:** {reason}\n**Critic Suggestion:** {suggestion}")
                            
                            # Add critic feedback to context
                            critic_msg = f"[Critic]: {reason}. {suggestion}. Restate your last point with a formal definition before continuing."
                            self.context.add_message("user", f"[{current_agent.name}]: {content}")
                            self.context.add_message("user", critic_msg)
                            
                            # Agent retries
                            print(f"\n{current_agent.name} (Retrying): ", end="", flush=True)
                            if self.semaphore:
                                async with self.semaphore:
                                    content, action = await current_agent.generate_response(self.context)
                            else:
                                content, action = await current_agent.generate_response(self.context)
                                
                            self.last_activity_time = time.time()
                            if not content.strip():
                                break
                        else:
                            print(f"[Critic] ACCEPT: {reason}")
                            last_suggestion = suggestion
                            self.consecutive_stalls = 0
                            break
                    
                    if rejections >= max_rejections:
                        self.consecutive_stalls += 1
                        last_suggestion = ""
                
                if content.strip():
                    break
            
            if not content.strip():
                print(f"\n[Error] {current_agent.name} failed to generate a response. Skipping turn.")
                await self._write_log("System", f"[Error] {current_agent.name} failed to generate a response. Turn skipped.")
                # Select next agent anyway to avoid full stall unless consecutive_stalls triggers it
                current_agent = await self._select_next_agent(last_suggestion)
                continue

            # Success: Record stats and add to context
            self.agent_stats[current_agent.name] += 1
            if current_agent.name == self.last_agent_name:
                self.consecutive_turns += 1
            else:
                self.last_agent_name = current_agent.name
                self.consecutive_turns = 1
                
            self.context.add_message("user", f"[{current_agent.name}]: {content}")
            
            # Log to file
            await self._write_log(current_agent.name, content)
            
            # Process actions
            await self._handle_action(current_agent, content, action)
            
            # Memory Extraction
            if self.memory and self.memory_config.get("enabled", False):
                interval = self.memory_config.get("extract_every_n_turns", 3)
                if self.current_turn % interval == 0:
                    # Non-blocking extraction
                    asyncio.create_task(self.memory.extract_and_store(
                        content, 
                        self.config.get("topic", ""), 
                        self.session_id, 
                        current_agent.name, 
                        self.current_turn
                    ))
            
            # Termination Check
            if await self._should_terminate(action):
                print(f"\n[Terminating Session: {self.final_verdict}]")
                await self._write_log("System", f"Session terminated. Reason: {self.final_verdict}")
                break
            
            # Next turn preparation
            current_agent = await self._select_next_agent(last_suggestion)
            
            # Small delay for readability
            await asyncio.sleep(1)
            
        # Final Summary
        await self.write_summary()
        if self.memory and self.memory_config.get("enabled", False):
            await self.memory.end_session(self.session_id, self.current_turn, self.final_verdict)

    async def write_summary(self):
        """Writes a final summary of the session to the log file."""
        most_active_agent = max(self.agent_stats, key=self.agent_stats.get) if self.agent_stats else "N/A"
        
        summary = (
            "## Session Summary\n\n"
            f"- **Total Turns:** {self.current_turn}\n"
            f"- **Most Active Agent:** {most_active_agent}\n"
            f"- **Critic Interventions:** {self.critic_interventions}\n"
            f"- **Final Verdict:** {self.final_verdict}\n"
            "\n### Agent Participation stats:\n"
        )
        for agent_name, turn_count in self.agent_stats.items():
            summary += f"- **{agent_name}**: {turn_count} successful turns\n"
            
        async with aiofiles.open(self.log_file, mode='a', encoding='utf-8') as f:
            await f.write(f"\n---\n\n{summary}")
        
        print(f"\n[Session Summary written to {self.log_file}]")
