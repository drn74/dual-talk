# main.py

import asyncio
import time
import aiofiles
import httpx
import json
import sys

from models.context import ContextManager, ContextStrategy
from models.agent import Agent
from models.critic import CriticAgent
from models.orchestrator import Orchestrator
from utils.memory import MemoryAgent
from models.session_runner import SessionRunner
from models.synthesis_agent import SynthesisAgent
from utils.topic_router import TopicRouter

async def check_ollama_connection():
    try:
        async with httpx.AsyncClient() as client:
            # Check if Ollama is running at localhost:11434
            response = await client.get("http://localhost:11434", timeout=5.0)
            if response.status_code == 200:
                return True
    except Exception:
        pass
    return False

async def show_memory(db_path: str, model: str):
    memory_agent = MemoryAgent(db_path, model)
    await memory_agent.initialize()
    deliverables = await memory_agent.get_all_deliverables()
    if not deliverables:
        print("\n[Memory] No artifacts found in database.")
        return
    
    print(f"\n=== Memory Inventory ({len(deliverables)} artifacts) ===")
    for d in deliverables:
        print(f"\n- [{d['topic']}] {d['agent_name']} (Turn {d['turn_number']})")
        print(f"  Type: {d['artifact_type']}")
        print(f"  Concept: {d['key_concept']}")
        print(f"  Notation: {d['formal_notation']}")
    print("\n" + "="*40)

def load_agents(config, model_name):
    agents_list = []
    raw_agents = config.get("agents", [])
    
    # Backward compatibility for agent_a and agent_b
    if not raw_agents:
        if "agent_a" in config:
            a = config["agent_a"]
            a["name"] = a.get("name", "Agent A")
            raw_agents.append(a)
        if "agent_b" in config:
            b = config["agent_b"]
            b["name"] = b.get("name", "Agent B")
            raw_agents.append(b)
            
    if len(raw_agents) < 2:
        return []

    # Normalize talk_ratios
    total_ratio = sum(float(a.get("talk_ratio", 0.5)) for a in raw_agents)
    
    for agent_cfg in raw_agents:
        name = agent_cfg.get("name", f"Agent {len(agents_list)+1}")
        persona = agent_cfg.get("persona", "Generic Expert")
        temp = float(agent_cfg.get("temperature", 0.7))
        top_p = float(agent_cfg.get("top_p", 0.9))
        raw_ratio = float(agent_cfg.get("talk_ratio", 0.5))
        talk_ratio = raw_ratio / total_ratio
        role_tags = agent_cfg.get("role_tags", [])
        
        agent = Agent(name=name, persona=persona, model=model_name, 
                      temperature=temp, top_p=top_p, 
                      talk_ratio=talk_ratio, role_tags=role_tags)
        agents_list.append(agent)
    return agents_list

async def main():
    print("=== Llama-Dual-Talk V2 ===")
    
    # Configuration from config.json
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        print("[Error] config.json not found!")
        return

    model_name = config.get("model", "llama3.2:3b")
    memory_config = config.get("memory", {})
    db_path = memory_config.get("db_path", "memory.db")
    topic = config.get("topic", "Artificial Intelligence")
    goal = config.get("goal", "Find an innovative application")

    # CLI Command: --show-memory
    if "--show-memory" in sys.argv:
        await show_memory(db_path, model_name)
        return

    # Check Ollama connection before proceeding
    if not await check_ollama_connection():
        print("[Error] Cannot connect to Ollama at http://localhost:11434. Please ensure Ollama is running.")
        return

    # --- AUTO-PERSONA SELECTION ---
    auto_persona_cfg = config.get("auto_persona", {})
    if auto_persona_cfg.get("enabled", False) and not config.get("agents"):
        print(f"\n[Auto-Persona] Analyzing topic: '{topic}'...")
        router = TopicRouter(model=model_name)
        classification = await router.classify_topic(topic, goal)
        print(f"[Auto-Persona] Domain: {classification['primary_domain']} (Complexity: {classification['complexity']})")
        
        selected_personas = router.select_personas(
            classification, 
            n_agents=auto_persona_cfg.get("n_agents", 2),
            force_domains=auto_persona_cfg.get("force_domains"),
            exclude_domains=auto_persona_cfg.get("exclude_domains")
        )
        
        agent_configs = router.build_agent_configs(selected_personas)
        config["agents"] = agent_configs
        print(f"[Auto-Persona] Selected: {', '.join([p['name'] for p in selected_personas])}")
        
        if "--preview-personas" in sys.argv:
            print("\nPreview Mode - Selected Persona Details:")
            for p in selected_personas:
                print(f"- {p['name']} ({p['role']}): {p['persona_text'][:100]}...")
            return

        # Suggest strategy based on complexity
        if "strategy" not in config:
            if classification["complexity"] == "high":
                config["strategy"] = "full_history"
            elif classification["complexity"] == "low":
                config["strategy"] = "sliding_window"
            else:
                config["strategy"] = "summary_mode"
            print(f"[Auto-Persona] Suggested Strategy: {config['strategy']}")

    # Initialize Memory Agent
    memory_agent = None
    if memory_config.get("enabled", False):
        memory_agent = MemoryAgent(db_path, model_name)
        await memory_agent.initialize()

    parallel_config = config.get("parallel_sessions", {})
    if parallel_config.get("enabled", False):
        # --- PARALLEL MODE ---
        print("\n[Parallel Sessions Mode Enabled]")
        subtopics = parallel_config.get("subtopics", [])
        max_concurrent = parallel_config.get("max_concurrent", 2)
        semaphore = asyncio.Semaphore(max_concurrent)
        
        # Load all agents for lookup
        all_agents = load_agents(config, model_name)
        
        # Load Critic
        critic_config = config.get("critic", {})
        critic_agent = None
        if critic_config.get("enabled", False):
            critic_agent = CriticAgent(
                model=model_name,
                temperature=critic_config.get("temperature", 0.3),
                top_p=critic_config.get("top_p", 0.85),
                system_prompt=critic_config.get("system_prompt")
            )

        runners = []
        for st in subtopics:
            # Filter agents for this subtopic
            st_agent_names = st.get("agents", [])
            st_agents = [a for a in all_agents if a.name in st_agent_names]
            if not st_agents:
                st_agents = all_agents[:2] # Fallback
                
            runner = SessionRunner(
                subtopic_id=st["id"],
                topic=st["topic"],
                goal=config.get("goal", ""),
                agents=st_agents,
                critic=critic_agent,
                config=config,
                memory_agent=memory_agent,
                semaphore=semaphore
            )
            runners.append(runner)

        print(f"Executing {len(runners)} parallel sessions (max_concurrent: {max_concurrent})...")
        results = await asyncio.gather(*(r.run() for r in runners))

        # Synthesis
        if parallel_config.get("synthesis_on_completion", True):
            print("\n[Starting Synthesis Phase...]")
            synthesizer = SynthesisAgent(model=model_name)
            synthesis = await synthesizer.synthesize(results, config.get("goal", ""))
            contradictions = await synthesizer.detect_contradictions(results)
            final_doc = await synthesizer.produce_final_document(synthesis, contradictions, config.get("topic", ""))
            
            timestamp = int(time.time())
            synthesis_file = f"synthesis_{timestamp}.md"
            async with aiofiles.open(synthesis_file, mode='w', encoding='utf-8') as f:
                await f.write(final_doc)
            print(f"[Final Synthesis Document written to {synthesis_file}]")
        
    else:
        # --- SINGLE SESSION MODE ---
        strategy_str = config.get("strategy", "full_history").lower()
        if strategy_str == "sliding_window":
            strategy = ContextStrategy.SLIDING_WINDOW
        elif strategy_str == "summary_mode":
            strategy = ContextStrategy.SUMMARY_MODE
        else:
            strategy = ContextStrategy.FULL_HISTORY
            
        window_size = config.get("window_size", 10)
        summary_threshold = config.get("summary_threshold", 15)

        session_id = str(int(time.time()))
        if memory_agent:
            await memory_agent.start_session(session_id, topic, goal)
            print(f"[Memory] Initialized. Session ID: {session_id}")

        context_manager = ContextManager(
            strategy=strategy, 
            model=model_name,
            window_size=window_size, 
            summary_threshold=summary_threshold
        )
        
        if memory_agent and memory_config.get("inject_on_start", True):
            limit = memory_config.get("max_injected_memories", 5)
            memories = await memory_agent.retrieve_relevant(topic, limit)
            if memories:
                print(f"[Memory] Injecting {len(memories)} relevant artifacts.")
                mem_text = "Relevant formal definitions:\n"
                for m in memories:
                    mem_text += f"- {m['key_concept']} ({m['artifact_type']}): {m['formal_notation']}\n"
                context_manager.add_message("system", f"[Memory]: {mem_text}")

        context_manager.add_message("user", f"Topic: {topic}\nGoal: {goal}\nStart session.")
        
        agents_list = load_agents(config, model_name)
        if not agents_list:
            print("[Error] Failed to load agents.")
            return

        critic_config = config.get("critic", {})
        critic_agent = None
        if critic_config.get("enabled", False):
            critic_agent = CriticAgent(
                model=model_name,
                temperature=critic_config.get("temperature", 0.3),
                top_p=critic_config.get("top_p", 0.85),
                system_prompt=critic_config.get("system_prompt")
            )
        
        log_file = f"conversation_{session_id}.md"
        async with aiofiles.open(log_file, mode='w', encoding='utf-8') as f:
            await f.write(f"# Session: {topic}\n\n**Goal:** {goal}\n\n---\n\n")

        orchestrator = Orchestrator(
            agents=agents_list,
            critic=critic_agent,
            context=context_manager,
            config=config,
            log_file=log_file,
            memory_agent=memory_agent,
            session_id=session_id
        )
        
        try:
            await orchestrator.run()
        except KeyboardInterrupt:
            print("\n[Interrupted]")
            await orchestrator.write_summary()
            if memory_agent:
                await memory_agent.end_session(session_id, orchestrator.current_turn, "INTERRUPTED")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
