"""Web search agent for optional MCP-backed web search."""
import os
from typing import List, Dict, Optional

import requests


class WebSearchAgent:
    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv("WEB_SEARCH_API_URL")

    def search(self, query: str, limit: int = 5) -> List[Dict]:
        if not self.api_url:
            return []
        try:
            response = requests.get(
                self.api_url,
                params={"query": query, "limit": limit},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            return payload.get("results", []) if isinstance(payload, dict) else []
        except Exception:
            return []
