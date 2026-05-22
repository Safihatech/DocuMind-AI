"""Retrieval agent: performs vector + hybrid search + optional web search."""

import logging
from typing import List, Dict

from app.agents.web_search import WebSearchAgent
from app.core.embeddings import embed_texts

logger = logging.getLogger(__name__)


class RetrievalAgent:
    def __init__(self, vector_store, embeddings_model, web_search_url: str = None):
        self.vector_store = vector_store
        # Note: embeddings_model parameter kept for compatibility but not used
        # embed_texts() handles model loading/fallback internally
        self.web_search_agent = WebSearchAgent(api_url=web_search_url)

    def retrieve(self, query: str, top_k: int = 5, use_hybrid: bool = True, use_web: bool = False, user_id: int | None = None, document_id: int | None = None) -> Dict:
        """Retrieve documents using hybrid search and optionally web search."""
        logger.info("Searching ChromaDB for query: %s", query)
        try:
            embedding = embed_texts([query])[0]
        except Exception as e:
            logger.exception("ERROR in embed_texts: %s", e)
            raise
        vector_results = self.vector_store.query(embedding, top_k=top_k, user_id=user_id, document_id=document_id)

        if vector_results:
            logger.info("Chunks found: %d", len(vector_results))
            top_ids = [item.get('id') for item in vector_results[:3]]
            logger.info("Top retrieved ids: %s", top_ids)
        else:
            logger.warning("No vector results found for query: %s", query)

        # If vector retrieval returns nothing, fall back to keyword search to preserve context.
        if not vector_results:
            keyword_results = self.vector_store.keyword_search(query, top_k=top_k, user_id=user_id, document_id=document_id)
            logger.info("Keyword fallback results: %d", len(keyword_results))
            return {"documents": keyword_results, "web_results": []}

        if not use_hybrid:
            local_results = vector_results
        else:
            keyword_results = self.vector_store.keyword_search(query, top_k=top_k, user_id=user_id, document_id=document_id)
            combined = {item["id"]: item for item in vector_results}

            for item in keyword_results:
                if item["id"] in combined:
                    combined[item["id"]]["score"] = combined[item["id"]].get("score", 0) + item.get("score", 0)
                else:
                    combined[item["id"]] = item

            local_results = sorted(combined.values(), key=lambda item: item.get("score", 0), reverse=True)[:top_k]

        web_results = []
        if use_web:
            web_results = self.web_search_agent.search(query, limit=top_k)

        return {"documents": local_results, "web_results": web_results}
