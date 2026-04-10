import enum
import httpx

class ContextStrategy(enum.Enum):
    FULL_HISTORY = "full_history"
    SLIDING_WINDOW = "sliding_window"
    SUMMARY_MODE = "summary_mode"

class ContextManager:
    def __init__(self, strategy: ContextStrategy, model: str = "llama3.2:3b", window_size: int = 10, summary_threshold: int = 15):
        self.strategy = strategy
        self.messages = []
        self.model = model
        self.window_size = window_size
        self.summary_threshold = summary_threshold
        self.system_prompt = (
            "You are a Senior Professional in a brainstorming session with another colleague. "
            "You will see the conversation as a transcript labeled with names like [Agent A] and [Agent B]. "
            "Be concise, analytical, and respond directly to your colleague's latest points. "
            "If you need to look up information on the web before answering, you can use the command: SEARCH: \"your query\" "
            "(exactly in this format, with quotes). "
            "When you believe the goal has been fully achieved or there is nothing more useful to add, "
            "you must write the exact command: STATUS: COMPLETED"
        )
        self.messages.append({"role": "system", "content": self.system_prompt})
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        
    async def get_context(self) -> list[dict]:
        if self.strategy == ContextStrategy.FULL_HISTORY:
            return self.messages
        elif self.strategy == ContextStrategy.SLIDING_WINDOW:
            if len(self.messages) <= self.window_size + 1:
                return self.messages
            else:
                return [self.messages[0]] + self.messages[-self.window_size:]
        elif self.strategy == ContextStrategy.SUMMARY_MODE:
            if len(self.messages) > self.summary_threshold:
                await self.summarize_context()
            return self.messages
        return self.messages

    async def summarize_context(self):
        if len(self.messages) <= 4:
            return
            
        system_msg = self.messages[0]
        recent_msgs = self.messages[-3:]
        msgs_to_summarize = self.messages[1:-3]
        
        summary_prompt_text = "Summarize very concisely the following key points of the past conversation to keep useful context for the continuation:\n\n"
        for msg in msgs_to_summarize:
            summary_prompt_text += f"{msg['role']}: {msg['content']}\n"
            
        # Manually format for Llama 3.2
        formatted_prompt = (
            f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{summary_prompt_text}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": self.model,
                        "prompt": formatted_prompt,
                        "raw": True,
                        "stream": False
                    },
                    timeout=60.0
                )
                if response.status_code == 200:
                    data = response.json()
                    summary_text = data.get("response", "").strip()
                    self.messages = [
                        system_msg,
                        {"role": "system", "content": f"Summary of previous messages: {summary_text}"}
                    ] + recent_msgs
        except Exception as e:
            print(f"\n[System] Error during summarization: {e}")
