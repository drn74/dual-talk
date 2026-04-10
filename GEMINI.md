# GEMINI.md - Llama-Dual-Talk V2 (Full Protocol)

## Project Overview
**Llama-Dual-Talk V2** is an advanced asynchronous multi-agent orchestration system for local LLMs (Ollama). It simulates complex brainstorming, formal specification sessions, and roleplay through a modular architecture supporting quality control, long-term memory, and parallel processing.

## Architecture & Implementation Details

### Core Technologies
- **LLM Engine:** Ollama (default: `llama3.2:3b`).
- **Persistence:** SQLite (`aiosqlite`) for memory and artifacts.
- **Async Engine:** `asyncio`, `httpx`, `aiofiles`.

### 1. Multi-Agent Orchestration
The system supports N domain agents with specialized roles.
- **Orchestrator:** Manages turn-taking (Round Robin, Weighted, Critic-Directed). It handles the main dialogue loop and special actions (SEARCH, STATUS).
- **Agent:** Handles Llama 3.2 raw prompt formatting using special tokens (`<|begin_of_text|>`, etc.) and manages streaming responses.
- **Critic Agent:** Analyzes every response for quality via JSON schema enforcement, rejecting vague or non-formal output.

### 2. Context Management (`models/context.py`)
Three strategies are implemented to manage token limits effectively:
- **FULL_HISTORY:** Sends the entire transcript for high-complexity tasks.
- **SLIDING_WINDOW:** Keeps only the last `N` messages, discarding older ones to save tokens.
- **SUMMARY_MODE:** Periodically compresses old history into a semantic summary using an LLM-powered summarization tool.

### 3. SQLite Memory & Artifacts (`utils/memory.py`)
- **Persistence:** Stores sessions and extracted "deliverables" (FSMs, Math, Code) in `memory.db`.
- **Extraction:** An LLM-driven process identifies key concepts and formal notations from agent responses.
- **Injection:** Relevant historical artifacts are retrieved and injected into the system prompt of new sessions.
- **CLI:** `--show-memory` prints the current inventory of formal deliverables.

### 4. Parallel Sessions & Synthesis
- **Subtopics:** Splitting a complex goal into parallel sessions running on isolated context via `SessionRunner`.
- **Concurrency:** Uses `asyncio.Semaphore` to limit concurrent LLM calls and protect local hardware resources.
- **Synthesis (`models/synthesis_agent.py`):** Aggregates outputs from parallel sessions, detects architectural contradictions, and produces a final unified document.

### 5. Auto-Persona Selection (`utils/topic_router.py`)
- **Topic Router:** LLM-powered classification of user input into domains (e.g., Technical, Creative, Scientific).
- **Persona Library:** 24+ pre-configured expert personas with specific temperatures and role tags.
- **Strategy Selection:** Automatically suggests a context strategy (Full vs. Summary) based on topic complexity.
- **CLI:** `--preview-personas` shows the selected experts before starting the session.

## File Structure
```text
├── main.py               # Entry point, CLI logic, and high-level flow
├── models/
│   ├── agent.py          # LLM interaction and prompt formatting
│   ├── context.py        # Context strategies (Full, Sliding, Summary)
│   ├── critic.py         # Response validation and artifact enforcement
│   ├── orchestrator.py   # Multi-agent loop controller
│   ├── session_runner.py # Logic for isolated parallel sessions
│   └── synthesis_agent.py # Aggregation and contradiction detection
├── utils/
│   ├── memory.py         # SQLite persistence and artifact extraction
│   ├── topic_router.py   # Domain classification and expert selection
│   ├── persona_library.py # Expert configurations
│   └── tools.py          # Search API (Serper.dev) integration
└── memory.db             # Local artifact database
```

## Setup & Execution
1. **Ollama:** Must be running locally on `11434`.
2. **Environment:** `pip install -r requirements.txt`.
3. **Run:** `python main.py`.
4. **Memory Inspect:** `python main.py --show-memory`.
5. **Preview:** `python main.py --preview-personas`.

## Security & Ethics
- **No Secrets:** `config.json` is gitignored. API keys must be handled via environment variables or ignored config.
- **Local-First:** All LLM processing is local via Ollama, ensuring data privacy.
