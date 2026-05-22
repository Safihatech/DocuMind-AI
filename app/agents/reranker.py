"""Re-ranker agent: re-ranks retrieved passages using lexical and heuristic scoring."""

from typing import List, Dict


class Reranker:
    def __init__(self):
        pass

    def rerank(self, query: str, candidates: List[Dict]) -> List[Dict]:
        """Re-rank candidates by relevance score.

        Scoring factors:
        - Query term frequency in candidate text
        - Candidate similarity/distance (if available from vector store)
        - Metadata recency (if available)
        """
        lower_query = query.lower()
        query_tokens = lower_query.split()
        scored = []

        for candidate in candidates:
            text = candidate.get("text", "").lower()
            # Term frequency score
            tf_score = sum(text.count(tok) for tok in query_tokens)
            # Bonus for query appearing as phrase
            if lower_query in text:
                tf_score += 10
            # Inverse distance (if from vector store)
            distance_score = 0
            if "distance" in candidate:
                distance_score = max(0, 1.0 - candidate["distance"])
            # Normalize and combine
            total_score = tf_score * 0.6 + distance_score * 0.4
            candidate["rerank_score"] = total_score
            scored.append(candidate)

        return sorted(scored, key=lambda item: item.get("rerank_score", 0), reverse=True)
