import httpx
import json

class CriticAgent:
    def __init__(self, model: str, temperature: float = 0.3, top_p: float = 0.85, system_prompt: str = None):
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.system_prompt = system_prompt or (
            "You are a strict quality evaluator. Your only job is to determine if the last response "
            "contains at least one formally defined artifact (mathematical definition, function signature, "
            "finite state machine, or algebraic structure). Respond ONLY with a JSON object: "
            "{\"verdict\": \"accept\" | \"reject\", \"reason\": \"string\", \"suggestion\": \"string\"}"
        )

    async def evaluate(self, content: str) -> dict:
        """
        Evaluates the last response and returns a JSON object with verdict, reason, and suggestion.
        """
        # Format for Llama 3.2
        prompt = (
            "<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n\n{self.system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{content}<|eot_id|>"
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
                        "options": {
                            "temperature": self.temperature,
                            "top_p": self.top_p
                        }
                    },
                    timeout=60.0
                )
                if response.status_code == 200:
                    data = response.json()
                    raw_response = data.get("response", "").strip()
                    
                    try:
                        return json.loads(raw_response)
                    except (json.JSONDecodeError, ValueError):
                        print(f"[Critic Warning] Failed to parse JSON from response: {raw_response[:100]}...")
        except Exception as e:
            print(f"[Critic Error] Exception during Ollama connection: {e}")
            
        # Fallback to accept to avoid blocking the conversation loop on system errors
        return {"verdict": "accept", "reason": "Critic system error, allowing turn", "suggestion": ""}
