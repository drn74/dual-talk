import httpx
import sys
import re
import json

from models.context import ContextManager

class Agent:
    def __init__(self, name: str, persona: str, model: str = "llama3.2:3b", 
                 temperature: float = 0.7, top_p: float = 0.9, 
                 talk_ratio: float = 0.5, role_tags: list[str] = None):
        self.name = name
        self.persona = persona
        self.model = model
        self.temperature = temperature
        self.top_p = top_p
        self.talk_ratio = talk_ratio
        self.role_tags = role_tags if role_tags else []
        self.search_regex = re.compile(r'(?i)SEARCH:\s*["\'«](.*?)["\'»]')
        self.termination_regex = re.compile(r'(?i)STATUS:\s*COMPLETED')

    def is_relevant_for(self, topic: str) -> bool:
        """Determines if the agent is relevant for a given topic based on its role_tags."""
        if not self.role_tags:
            return True # Assume relevant if no tags specified
        topic_lower = topic.lower()
        return any(tag.lower() in topic_lower for tag in self.role_tags)

    def _format_llama_prompt(self, messages: list[dict]) -> str:
        """Formats a list of messages into the Llama 3.2 text prompt format."""
        prompt = "<|begin_of_text|>"
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt += f"<|start_header_id|>{role}<|end_header_id|>\n\n{content}<|eot_id|>"
        prompt += "<|start_header_id|>assistant<|end_header_id|>\n\n"
        return prompt

    async def generate_response(self, context_manager: ContextManager) -> tuple[str, str | None]:
        """
        Calls Ollama API with streaming using /api/generate and raw Llama 3.2 formatting, 
        parses for commands. Injects its specific persona as a temporary system message.
        """
        print(f"\n{self.name}: ", end="", flush=True)
        
        # Get base history
        messages = await context_manager.get_context()
        
        # Prepend the specific identity to the messages for this turn ONLY
        # This ensures the model knows WHO it is during the response generation
        persona_msg = {"role": "system", "content": f"YOUR IDENTITY: {self.persona}"}
        active_messages = [persona_msg] + messages
        
        raw_prompt = self._format_llama_prompt(active_messages)
        
        full_response = ""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": raw_prompt,
                        "raw": True,
                        "stream": True,
                        "options": {
                            "temperature": self.temperature,
                            "top_p": self.top_p
                        }
                    },
                    timeout=120.0
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        print(f"\n[API Error: {response.status_code}] {error_text.decode()}")
                        return full_response, None
                        
                    async for chunk in response.aiter_lines():
                        if chunk:
                            try:
                                data = json.loads(chunk)
                                content = data.get("response", "")
                                full_response += content
                                print(content, end="", flush=True)
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            print(f"\n[Exception during Ollama connection: {e}]")
            
        print() # Newline after response is fully streamed
        
        # Parse for actions
        search_match = self.search_regex.search(full_response)
        if search_match:
            return full_response, f"search:{search_match.group(1).strip()}"
            
        termination_match = self.termination_regex.search(full_response)
        if termination_match:
            return full_response, "completed"
            
        return full_response, None
