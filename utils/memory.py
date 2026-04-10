import aiosqlite
import json
import httpx
from datetime import datetime

class MemoryAgent:
    def __init__(self, db_path: str, model: str):
        self.db_path = db_path
        self.model = model

    async def initialize(self):
        """Creates the necessary tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    topic TEXT,
                    goal TEXT,
                    model TEXT,
                    started_at TIMESTAMP,
                    ended_at TIMESTAMP,
                    turn_count INTEGER,
                    verdict TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS deliverables (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    agent_name TEXT,
                    turn_number INTEGER,
                    content TEXT,
                    artifact_type TEXT,
                    formal_notation TEXT,
                    key_concept TEXT,
                    created_at TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            await db.commit()

    async def start_session(self, session_id: str, topic: str, goal: str):
        """Records the start of a new session."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO sessions (id, topic, goal, model, started_at) VALUES (?, ?, ?, ?, ?)",
                (session_id, topic, goal, self.model, datetime.now().isoformat())
            )
            await db.commit()

    async def end_session(self, session_id: str, turn_count: int, verdict: str):
        """Updates the session record with end time and results."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE sessions SET ended_at = ?, turn_count = ?, verdict = ? WHERE id = ?",
                (datetime.now().isoformat(), turn_count, verdict, session_id)
            )
            await db.commit()

    async def extract_and_store(self, content: str, topic: str, session_id: str, agent_name: str, turn_number: int):
        """Calls Ollama to extract formal artifacts and stores them in the DB."""
        prompt = (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n\n"
            "Extract all formally defined artifacts from the following text. "
            "Return ONLY a JSON array where each item has: "
            "{\"artifact_type\": string, \"formal_notation\": string, \"key_concept\": string}. "
            "If no formal artifacts are found, return an empty array [].<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{content}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "format": "json",
                        "raw": True,
                        "stream": False,
                        "options": {"temperature": 0.1}
                    },
                    timeout=60.0
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_resp = data.get("response", "").strip()
                    
                    try:
                        artifacts = json.loads(raw_resp)
                        
                        if isinstance(artifacts, list) and artifacts:
                            async with aiosqlite.connect(self.db_path) as db:
                                for art in artifacts:
                                    await db.execute(
                                        """INSERT INTO deliverables 
                                        (session_id, agent_name, turn_number, content, artifact_type, formal_notation, key_concept, created_at) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                        (session_id, agent_name, turn_number, content, 
                                         art.get("artifact_type"), art.get("formal_notation"), 
                                         art.get("key_concept"), datetime.now().isoformat())
                                    )
                                await db.commit()
                                print(f"\n[Memory] Extracted and stored {len(artifacts)} formal artifacts.")
                    except (json.JSONDecodeError, ValueError):
                        pass
        except Exception as e:
            print(f"\n[Memory Error] Extraction failed: {e}")

    async def retrieve_relevant(self, topic: str, limit: int = 5) -> list[dict]:
        """Retrieves relevant artifacts from previous sessions on the same topic."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            # Simple keyword match on topic for now
            async with db.execute(
                """SELECT artifact_type, formal_notation, key_concept FROM deliverables 
                JOIN sessions ON deliverables.session_id = sessions.id 
                WHERE sessions.topic LIKE ? 
                ORDER BY deliverables.created_at DESC LIMIT ?""",
                (f"%{topic}%", limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_all_deliverables(self) -> list[dict]:
        """Utility for --show-memory."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT d.*, s.topic FROM deliverables d JOIN sessions s ON d.session_id = s.id ORDER BY d.created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
