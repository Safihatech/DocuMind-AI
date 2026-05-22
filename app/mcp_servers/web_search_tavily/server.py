"""MCP wrapper for Tavily web search.

This wrapper exposes a simplified search endpoint. When TAVILY_API_KEY is not configured,
returns a placeholder response for development.
"""
import os
from fastapi import FastAPI, HTTPException, Query
import requests

app = FastAPI()


@app.get("/ping")
async def ping():
    return {"status": "ok"}


@app.get("/search")
async def search(query: str = Query(...), limit: int = Query(5, ge=1, le=20)):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {
            "query": query,
            "results": [
                {"title": "Placeholder Search Result", "url": "https://example.com", "snippet": "This is a placeholder because TAVILY_API_KEY is not configured."}
            ][:limit],
        }

    endpoint = "https://api.tavily.io/v1/search"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"query": query, "top_k": limit}
    response = requests.get(endpoint, headers=headers, params=params, timeout=15)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()
