import httpx
import asyncio
import json

async def test_multi_assistant():
    url = "http://localhost:11434/api/chat"
    model = "llama3.2:3b"
    
    # Case 1: Two assistant messages in a row
    messages = [
        {"role": "system", "content": "You are Agent B. Respond to Agent A."},
        {"role": "user", "content": "Topic: Mars colony."},
        {"role": "assistant", "content": "Agent A: I think we should build greenhouses."}
    ]
    
    print("--- Testing with Assistant role for Agent A ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "model": model,
            "messages": messages,
            "stream": False
        }, timeout=30.0)
        print(f"Response: {response.json().get('message', {}).get('content')}")

    # Case 2: Agent A as 'user'
    messages_fixed = [
        {"role": "system", "content": "You are Agent B. Respond to Agent A."},
        {"role": "user", "content": "Topic: Mars colony."},
        {"role": "user", "content": "Agent A: I think we should build greenhouses."}
    ]
    
    print("\n--- Testing with User role for Agent A ---")
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json={
            "model": model,
            "messages": messages_fixed,
            "stream": False
        }, timeout=30.0)
        print(f"Response: {response.json().get('message', {}).get('content')}")

if __name__ == "__main__":
    asyncio.run(test_multi_assistant())
