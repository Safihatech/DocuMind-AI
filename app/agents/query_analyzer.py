"""Query Analyzer: expands, detects intent, decides retrieval strategy."""

from typing import Dict


class QueryAnalyzer:
    def __init__(self):
        pass

    def analyze(self, query: str) -> Dict:
        """Analyze query to determine retrieval strategy.

        Returns:
            - query: normalized query string
            - top_k: number of documents to retrieve
            - use_hybrid: whether to use hybrid search (vector + keyword)
            - is_follow_up: whether query appears to be a follow-up
            - use_web_search: whether to augment with web search
        """
        normalized = query.strip().lower()
        is_follow_up = any(token in normalized for token in ["also", "follow up", "more", "clarify", "what about", "how about"])
        # Only use web search when the user explicitly asks for current events or web results.
        use_web = any(token in normalized for token in ["search online", "web search", "latest news", "current events", "current", "latest", "today"])
        return {
            "query": query.strip(),  # preserve original case for embedding
            "top_k": 5,
            "use_hybrid": True,
            "is_follow_up": is_follow_up,
            "use_web_search": use_web,
        }
