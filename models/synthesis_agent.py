import httpx
import json

class SynthesisAgent:
    def __init__(self, model: str, temperature: float = 0.4):
        self.model = model
        self.temperature = temperature

    async def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        prompt = (
            "<|begin_of_text|>"
            f"<|start_header_id|>system<|end_header_id|>\n\n{system_prompt}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{user_prompt}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "raw": True,
                        "stream": False,
                        "options": {"temperature": self.temperature}
                    },
                    timeout=120.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "").strip()
        except Exception as e:
            print(f"[Synthesis Error] {e}")
        return ""

    async def synthesize(self, sessions_results: list[dict], goal: str) -> str:
        """Merges results from multiple sessions into a unified summary."""
        results_text = ""
        for res in sessions_results:
            results_text += f"\n### Session: {res['subtopic_id']} (Topic: {res['topic']})\n{res['deliverables']}\n"

        system_prompt = (
            "You are a synthesis expert. Your task is to merge the following subtopic deliverables "
            "into a single, coherent technical summary that fulfills the overall goal."
        )
        user_prompt = f"Goal: {goal}\n\nDeliverables from sub-sessions:\n{results_text}"
        
        return await self._call_ollama(system_prompt, user_prompt)

    async def detect_contradictions(self, sessions_results: list[dict]) -> list[dict]:
        """Identifies contradictions between different session deliverables."""
        results_text = ""
        for res in sessions_results:
            results_text += f"\n### Session: {res['subtopic_id']}\n{res['deliverables']}\n"

        system_prompt = (
            "Identify any mathematical, logical, or architectural contradictions between the following session deliverables. "
            "Return ONLY a JSON array of objects: [{\"id_a\": string, \"id_b\": string, \"description\": string}]."
        )
        user_prompt = f"Session deliverables:\n{results_text}"
        
        raw_resp = await self._call_ollama(system_prompt, user_prompt)
        try:
            start = raw_resp.find('[')
            end = raw_resp.rfind(']') + 1
            if start != -1 and end != 0:
                return json.loads(raw_resp[start:end])
        except:
            pass
        return []

    async def produce_final_document(self, synthesis: str, contradictions: list, topic: str) -> str:
        """Produces the final Markdown document."""
        contradictions_text = "None detected."
        if contradictions:
            contradictions_text = ""
            for c in contradictions:
                contradictions_text += f"- **Between {c.get('id_a')} and {c.get('id_b')}**: {c.get('description')}\n"

        document = (
            f"# Final Synthesis: {topic}\n\n"
            "## Executive Summary\n"
            f"{synthesis}\n\n"
            "## Contradictions & Conflicts\n"
            f"{contradictions_text}\n\n"
            "## Open Questions & Next Steps\n"
            "- Review the formal definitions for consistency.\n"
            "- Prototype the error correction algebra.\n"
            "- Finalize the bootstrapping state machine transitions.\n"
        )
        return document
