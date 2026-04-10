import httpx
import logging
import json

def perform_web_search(query: str, api_key: str = "") -> str:
    """
    Performs a web search using Serper.dev (Google Search API) and returns formatted results.
    """
    if not api_key:
        return "Web Search Results: [Disabled] Serper.dev API key is missing in config.json."
        
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    payload = json.dumps({
        "q": query,
        "num": 3
    })
    
    try:
        with httpx.Client() as client:
            response = client.post(url, headers=headers, data=payload, timeout=15.0)
            response.raise_for_status()
            data = response.json()
            
            # Serper.dev results are in the 'organic' list
            organic_results = data.get("organic", [])
            if not organic_results:
                return "No search results found."
                
            formatted_results = []
            for item in organic_results:
                title = item.get("title", "No Title")
                snippet = item.get("snippet", "No Snippet")
                link = item.get("link", "No Link")
                formatted_results.append(f"Title: {title}\nSnippet: {snippet}\nURL: {link}")
                
            return "Web Search Results:\n" + "\n\n".join(formatted_results)
    except httpx.HTTPStatusError as e:
        return f"HTTP error during web search: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"Error during web search: {str(e)}"
