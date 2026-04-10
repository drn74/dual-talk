import asyncio
import time
import aiofiles
from models.orchestrator import Orchestrator
from models.context import ContextManager, ContextStrategy

class SessionRunner:
    def __init__(self, subtopic_id: str, topic: str, goal: str, agents: list, critic, config: dict, memory_agent, semaphore: asyncio.Semaphore):
        self.subtopic_id = subtopic_id
        self.topic = topic
        self.goal = goal
        self.agents = agents
        self.critic = critic
        self.config = config
        self.memory = memory_agent
        self.semaphore = semaphore
        
        self.timestamp = int(time.time())
        self.log_file = f"conversation_{self.timestamp}_{self.subtopic_id}.md"

    async def run(self) -> dict:
        """Runs a single conversation session for a subtopic."""
        model_name = self.config.get("model", "llama3.2:3b")
        strategy_str = self.config.get("strategy", "full_history").lower()
        if strategy_str == "sliding_window":
            strategy = ContextStrategy.SLIDING_WINDOW
        elif strategy_str == "summary_mode":
            strategy = ContextStrategy.SUMMARY_MODE
        else:
            strategy = ContextStrategy.FULL_HISTORY
        
        context_manager = ContextManager(
            strategy=strategy,
            model=model_name,
            window_size=self.config.get("window_size", 10),
            summary_threshold=self.config.get("summary_threshold", 15)
        )
        
        # Inject memories if enabled
        memory_config = self.config.get("memory", {})
        if self.memory and memory_config.get("inject_on_start", True):
            limit = memory_config.get("max_injected_memories", 5)
            memories = await self.memory.retrieve_relevant(self.topic, limit)
            if memories:
                mem_text = "Relevant formal definitions from previous sessions on this topic:\n"
                for m in memories:
                    mem_text += f"- {m['key_concept']} ({m['artifact_type']}): {m['formal_notation']}\n"
                context_manager.add_message("system", f"[Memory]: {mem_text}")

        context_manager.add_message("user", f"Sub-Topic: {self.topic}\nGoal: {self.goal}\nStart the brainstorming session.")
        
        # Log Header
        async with aiofiles.open(self.log_file, mode='w', encoding='utf-8') as f:
            await f.write(f"# Session: {self.subtopic_id}\n\n**Topic:** {self.topic}\n**Goal:** {self.goal}\n\n---\n\n")

        # Initialize Orchestrator
        # Note: We pass the semaphore to Orchestrator or handle it here?
        # Let's wrap generate_response of agents to respect the semaphore or 
        # modify Orchestrator to respect it. 
        # Simple approach: modify Orchestrator to take an optional semaphore.
        
        orchestrator = Orchestrator(
            agents=self.agents,
            critic=self.critic,
            context=context_manager,
            config=self.config,
            log_file=self.log_file,
            memory_agent=self.memory,
            session_id=f"{self.timestamp}_{self.subtopic_id}",
            semaphore=self.semaphore
        )
        
        # In this implementation, I'll assume we might want to modify Orchestrator
        # but for now, we'll let it run. To strictly respect max_concurrent,
        # we'd need to semaphore the actual LLM calls.
        
        await orchestrator.run()
        
        # Extract deliverables from context for synthesis
        messages = await context_manager.get_context()
        all_content = "\n".join([m['content'] for m in messages if m['role'] == 'user'])
        
        return {
            "subtopic_id": self.subtopic_id,
            "topic": self.topic,
            "deliverables": all_content,
            "turn_count": orchestrator.current_turn,
            "verdict": orchestrator.final_verdict
        }
