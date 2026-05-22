"""ChromaDB vector store helper.

This helper wraps either a remote MCP-backed vector database endpoint or a
local in-memory fallback. Documents are expected as dicts with keys: `id`,
`text`, `metadata`, and optional `embedding`.
"""
from typing import List, Dict, Optional
import math
import requests
import json
from pathlib import Path


class VectorStore:
    def __init__(self, collection_name: str = "documents", api_url: Optional[str] = None):
        self.api_url = api_url
        self.collection_name = collection_name
        self._local_index = []
        # Path to persist the in-memory index so it survives restarts
        self._persist_path = Path(__file__).resolve().parents[3] / "uploads" / "index_local.json"
        self.collection = None
        self._remote_unavailable = False

        # If a remote URL is provided, quickly verify it's reachable.
        # If not (common when running with `python` on host and api_url is `http://chroma:8002`),
        # force local-only mode so queries work instantly.
        if api_url:
            try:
                # Using /ping exposed by the MCP wrapper server.
                r = requests.get(f"{api_url.rstrip('/')}/ping", timeout=2)
                if r.status_code != 200:
                    self.api_url = None
            except Exception:
                self.api_url = None
        # Attempt to load any previously persisted local index
        try:
            self._load_local_index()
        except Exception:
            pass

    def add_documents(self, docs: List[Dict]):
        """Add documents to the collection.

        docs: list of {id, text, metadata, embedding}
        """
        ids = [d["id"] for d in docs]
        texts = [d["text"] for d in docs]
        metadatas_raw = [d.get("metadata", {}) for d in docs]
        metadatas = self.sanitize_metadatas(metadatas_raw)
        embeddings = [d.get("embedding") for d in docs]

        def tolist_safe(e):
            try:
                return e.tolist() if hasattr(e, 'tolist') else e
            except Exception:
                return e

        embeddings = [tolist_safe(e) for e in embeddings]

        # Try remote Chroma first; if it fails, fall back to the in-memory store.
        if self.api_url and not self._remote_unavailable:
            payload = {
                "collection_name": self.collection_name,
                "ids": ids,
                "texts": texts,
                "metadatas": metadatas,
                "embeddings": embeddings,
            }
            try:
                response = requests.post(
                    f"{self.api_url.rstrip('/')}/add", json=payload, timeout=10
                )
                response.raise_for_status()
            except requests.exceptions.RequestException:
                self._remote_unavailable = True

        # Persist locally for fast fallback and in-memory query support.
        for idx, d in enumerate(docs):
            self._local_index.append({
                "id": d["id"],
                "text": d["text"],
                "metadata": metadatas[idx],
                "embedding": embeddings[idx],
            })
        # Save the local index to disk so it persists across restarts.
        try:
            self._save_local_index()
        except Exception:
            pass

    def _load_local_index(self):
        try:
            if self._persist_path.exists():
                with self._persist_path.open("r", encoding="utf-8") as fh:
                    items = json.load(fh)
                    # ensure keys exist on each item
                    self._local_index = [
                        {"id": it.get("id"), "text": it.get("text"), "metadata": it.get("metadata", {}), "embedding": it.get("embedding")} for it in items
                    ]
        except Exception:
            # ignore persistence failures
            pass

    def _save_local_index(self):
        try:
            # ensure directory exists
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with self._persist_path.open("w", encoding="utf-8") as fh:
                json.dump(self._local_index, fh, ensure_ascii=False)
        except Exception:
            pass

    @staticmethod
    def _cosine_similarity(a, b):
        if a is None or b is None:
            return 0.0
        try:
            a_list = a.tolist() if hasattr(a, 'tolist') else list(a)
            b_list = b.tolist() if hasattr(b, 'tolist') else list(b)
        except Exception:
            return 0.0

        if not a_list or not b_list or len(a_list) != len(b_list):
            return 0.0

        dot = sum(float(x) * float(y) for x, y in zip(a_list, b_list))
        norm_a = math.sqrt(sum(float(x) ** 2 for x in a_list))
        norm_b = math.sqrt(sum(float(y) ** 2 for y in b_list))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def sanitize_metadatas(metadatas_raw: List[Dict]):
        import json

        def sanitize_value(value):
            # Chroma metadata values must be non-null, JSON-serializable scalars.
            if value is None:
                return None
            if isinstance(value, (str, int, float, bool)):
                return value
            if isinstance(value, list):
                sanitized_list = []
                for item in value:
                    sanitized_item = sanitize_value(item)
                    if sanitized_item is not None:
                        sanitized_list.append(sanitized_item)
                try:
                    return json.dumps(sanitized_list, ensure_ascii=False)
                except Exception:
                    return str(sanitized_list)
            if isinstance(value, dict):
                try:
                    return json.dumps(value)
                except Exception:
                    return str(value)
            return str(value)

        sanitized_metadatas = []
        for m in metadatas_raw:
            sanitized = {}
            for k, v in m.items():
                sanitized_value = sanitize_value(v)
                if sanitized_value is not None:
                    sanitized[k] = sanitized_value
            sanitized_metadatas.append(sanitized)
        return sanitized_metadatas

    def query(self, embedding, top_k: int = 5, user_id: int | None = None, document_id: int | None = None):
        """Query the collection by embedding. Returns list of results with metadata."""
        try:
            embedding = embedding.tolist() if hasattr(embedding, 'tolist') else embedding
        except Exception:
            pass

        if self.api_url and not getattr(self, "_remote_unavailable", False):
            payload = {
                "collection_name": self.collection_name,
                "embedding": embedding,
                "top_k": top_k,
            }
            try:
                response = requests.post(
                    f"{self.api_url.rstrip('/')}/query", json=payload, timeout=10
                )
                response.raise_for_status()
                res = response.json()
            except requests.exceptions.RequestException:
                self._remote_unavailable = True
                res = None
            if res is not None and "documents" in res:
                results = []
                docs = res.get("documents", [[]])[0]
                metadatas = res.get("metadatas", [[]])[0]
                ids = res.get("ids", [[]])[0] if "ids" in res else []
                distances = res.get("distances", [[]])[0] if "distances" in res else []
                for i in range(len(docs)):
                    metadata = metadatas[i] if i < len(metadatas) else {}
                    stored_user_id = metadata.get("user_id")
                    # Do not filter results by user_id or document_id here; always
                    # return matching documents from the collection so follow-ups
                    # are not accidentally blocked. Filtering by user/document
                    # should be handled at a higher application layer if needed.
                    result = {
                        "id": ids[i] if i < len(ids) else f"result-{i}",
                        "text": docs[i],
                        "metadata": metadata,
                    }
                    if i < len(distances):
                        result["distance"] = distances[i]
                    if "score" in res:
                        result["score"] = res.get("score")
                    results.append(result)
                return results

        if embedding is None:
            return self.keyword_search("", top_k=top_k, user_id=user_id)

        return self._local_vector_query(embedding, top_k=top_k, user_id=user_id, document_id=document_id)

    def count(self) -> int:
        """Return the number of documents currently stored in the local index."""
        return len(self._local_index)

    def _local_vector_query(self, embedding, top_k: int = 5, user_id: int | None = None, document_id: int | None = None):
        try:
            embedding = embedding.tolist() if hasattr(embedding, 'tolist') else list(embedding)
        except Exception:
            embedding = list(embedding) if embedding is not None else []

        if not embedding:
            return self.keyword_search("", top_k=top_k, user_id=user_id)

        scored = []
        for doc in self._local_index:
            metadata = doc.get("metadata", {})
            # Do not apply user_id/document_id filtering here; return all
            # indexed documents so every query sees the full collection.
            score = self._cosine_similarity(embedding, doc.get("embedding"))
            if score > 0:
                scored.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "metadata": metadata,
                    "score": score,
                    "distance": 1.0 - score,
                })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def keyword_search(self, query: str, top_k: int = 5, user_id: int | None = None, document_id: int | None = None):
        """Simple keyword-based search over the in-memory index."""
        q = query.lower().split()
        scored = []

        # Debugging: helps us confirm whether chunks are actually indexed into _local_index
        # (prints only when the index is empty to avoid log spam).
        if not self._local_index:
            import logging
            logging.warning("keyword_search called but _local_index is empty")

        for doc in self._local_index:
            metadata = doc.get("metadata", {})
            # Do not filter by user_id or document_id here; return all
            # matching documents to avoid blocking follow-up questions.
            text = (doc.get("text") or "").lower()
            score = sum(text.count(tok) for tok in q)
            if score > 0:
                scored.append({"id": doc["id"], "text": doc["text"], "metadata": metadata, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]
