# utils/topic_router.py

import json
import httpx
import random
from utils.persona_library import PERSONA_LIBRARY

class TopicRouter:
    def __init__(self, model: str):
        self.model = model

    async def classify_topic(self, topic: str, goal: str) -> dict:
        """Calls Ollama to classify the topic and goal into domains and required expertise."""
        prompt = (
            "<|begin_of_text|>"
            "<|start_header_id|>system<|end_header_id|>\n\n"
            "Classify the following topic and goal into domains and required expertise. "
            "Domains available: technical, scientific, philosophical, legal, creative, mathematical, humanities. "
            "Return ONLY JSON: {\"primary_domain\": string, \"secondary_domains\": list[string], \"required_roles\": list[string], \"recommended_agent_count\": int, \"complexity\": \"low\"|\"medium\"|\"high\"}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"Topic: {topic}\nGoal: {goal}<|eot_id|>"
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
                        "options": {"temperature": 0.2}
                    },
                    timeout=60.0
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_resp = data.get("response", "").strip()
                    try:
                        return json.loads(raw_resp)
                    except:
                        pass
        except Exception as e:
            print(f"[TopicRouter Error] Classification failed: {e}")
        
        # Fallback
        return {
            "primary_domain": "technical",
            "secondary_domains": [],
            "required_roles": ["expert"],
            "recommended_agent_count": 2,
            "complexity": "medium"
        }

    def select_personas(self, classification: dict, n_agents: int = 2, force_domains: list = None, exclude_domains: list = None) -> list[dict]:
        """Selects the optimal personas from the library based on the classification."""
        primary = classification.get("primary_domain", "technical")
        secondaries = classification.get("secondary_domains", [])
        
        selected = []
        available_domains = list(PERSONA_LIBRARY.keys())
        
        if force_domains:
            search_domains = force_domains
        else:
            search_domains = [primary] + secondaries
            
        if exclude_domains:
            search_domains = [d for d in search_domains if d not in exclude_domains]
            
        # Collect candidates
        candidates = []
        for d in search_domains:
            if d in PERSONA_LIBRARY:
                candidates.extend(PERSONA_LIBRARY[d])
        
        # If not enough candidates, add from other domains
        if len(candidates) < n_agents:
            for d in available_domains:
                if d not in search_domains and (not exclude_domains or d not in exclude_domains):
                    candidates.extend(PERSONA_LIBRARY[d])
        
        # Randomly select N agents from candidates
        if len(candidates) >= n_agents:
            selected = random.sample(candidates, n_agents)
        else:
            selected = candidates # Should not happen with 24 personas
            
        return selected

    def build_agent_configs(self, personas: list[dict]) -> list[dict]:
        """Converts selected personas into Agent configuration dictionaries."""
        configs = []
        # Calculate talk ratio
        ratio = 1.0 / len(personas) if personas else 0.5
        for p in personas:
            configs.append({
                "name": p["name"],
                "persona": p["persona_text"],
                "temperature": p["temperature"],
                "top_p": p["top_p"],
                "talk_ratio": ratio,
                "role_tags": p["role_tags"]
            })
        return configs
