# Llama-Dual-Talk V2 🤖🧠

**Llama-Dual-Talk V2** is an advanced multi-agent orchestration framework for **local LLMs (Ollama)**. It enables complex, structured dialogues between specialized AI agents, featuring autonomous quality control, long-term memory, and parallel subtopic processing.

Developed to simulate high-level brainstorming, formal specification drafting, and recursive architectural planning without cloud dependencies.

---

## 🏗️ System Architecture

```text
┌───────────────────────────────────────────────────────────┐
│                      TOPIC ROUTER                         │
│   (Classifies Topic, Selects Personas & Context Strategy) │
└──────────────┬─────────────────────────────┬──────────────┘
               │                             │
               ▼                             ▼
    ┌───────────────────────┐     ┌───────────────────────┐
    │    SINGLE SESSION     │     │   PARALLEL SESSIONS   │
    │   (One Orchestrator)  │     │   (N Session Runners) │
    └──────────┬────────────┘     └──────────┬────────────┘
               │                             │
               └──────────────┬──────────────┘
                              ▼
               ┌─────────────────────────────┐
               │        ORCHESTRATOR         │
               │ (Turns, Actions, Context)   │
               └──────────────┬──────────────┘
               ┌──────────────┴──────────────┐
        ┌──────▼──────┐               ┌──────▼──────┐
        │   AGENT A   │               │   AGENT B   │
        └──────┬──────┘               └──────┬──────┘
               └──────────────┬──────────────┘
                              ▼
               ┌─────────────────────────────┐
               │        CRITIC AGENT         │
               │ (Validation & Rejection)    │
               └──────────────┬──────────────┘
                              ▼
               ┌─────────────────────────────┐
               │        MEMORY AGENT         │
               │ (SQLite, Extraction, RAG)   │
               └──────────────┬──────────────┘
                              ▼
               ┌─────────────────────────────┐
               │       SYNTHESIS AGENT       │
               │ (Merging & Final Document)  │
               └─────────────────────────────┘
```

---

## ✨ Key Features

### 🚀 Advanced Orchestration
- **N-Agent Support:** Define multiple domain experts with specialized personas.
- **Dynamic Turn Taking:** Choose between *Round Robin*, *Weighted Probability*, or *Critic-Directed* selection.
- **Asynchronous Loop:** High-speed interactions powered by `asyncio` and `httpx`.

### 🔍 Quality & Formalism (Critic Agent)
- **Real-time Validation:** A specialized *Critic Agent* evaluates every turn using JSON enforcement.
- **Rejection Loop:** Vague or non-formal responses are rejected and sent back for refinement.
- **Artifact Enforcement:** Forces agents to produce concrete deliverables (Math, Code, FSMs).

### 🏛️ Long-Term Memory (SQLite)
- **Artifact Extraction:** Automatically identifies and stores formal definitions in a local SQLite database (`memory.db`).
- **Knowledge Injection:** Re-injects relevant historical artifacts into new sessions based on topic similarity.
- **Session Persistence:** Tracks conversation goals and outcomes across restarts.

### 🌐 Parallel Sessions & Synthesis
- **Subtopic Splitting:** Tackle massive projects by running subtopics in parallel isolated contexts via `SessionRunner`.
- **Synthesis Agent:** Aggregates parallel outputs, detects architectural contradictions, and generates a unified final document.
- **Resource Protection:** Global semaphores (`asyncio.Semaphore`) prevent local hardware overload (GPU/CPU).

### 🎭 Auto-Persona Selection
- **Topic Router:** Classifies your topic and automatically picks the best experts from a library of 24+ pre-configured personas.
- **Adaptive Strategy:** Recommends the best context management strategy (**Full History**, **Sliding Window**, or **Summary Mode**) based on topic complexity.

---

## 🛠️ Architecture

The system follows a modular **Research -> Strategy -> Execution** lifecycle:
1.  **Topic Router:** Classifies the domain and selects experts.
2.  **Memory Agent:** Injects relevant past knowledge from SQLite.
3.  **Context Manager:** Applies the selected context strategy (e.g., Summary Mode).
4.  **Orchestrator:** Manages the agent dialogue and turn-taking.
5.  **Critic:** Ensures high-quality output via real-time evaluation.
6.  **Synthesis Agent:** (In Parallel Mode) Produces the final unified deliverable.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+**
- **Ollama:** [Download Ollama](https://ollama.com/) (Ensure `llama3.2:3b` or your preferred model is pulled).
- **Serper.dev API Key:** (Optional) For web search capabilities.

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/your-username/llama-dual-talk-v2.git
    cd llama-dual-talk-v2
    ```
2.  Set up a virtual environment:
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # Linux/macOS
    source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Configuration
1.  Copy the example config:
    ```bash
    cp config.json.example config.json
    ```
2.  Edit `config.json` to set your **Topic**, **Goal**, and **Model**.

### Usage
- **Start Session:**
  ```bash
  python main.py
  ```
- **Preview Auto-Persona Selection:**
  ```bash
  python main.py --preview-personas
  ```
- **View Stored Memory:**
  ```bash
  python main.py --show-memory
  ```

---

## 📜 License
MIT License. Free to use for research and development.

## 🤝 Contributing
Contributions are welcome! Please open an issue or a pull request for any architectural improvements.
