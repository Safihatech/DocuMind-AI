"""Citation agent: formats citations and preserves metadata."""

from typing import List, Dict


class CitationAgent:
    def __init__(self):
        pass

    def format(self, docs: List[Dict]) -> List[Dict]:
        """Format documents as citations with metadata.

        Args:
            docs: List of document dicts from retrieval

        Returns:
            List of citation dicts with id, source, title, tags, snippet
        """
        formatted = []
        for idx, doc in enumerate(docs, start=1):
            metadata = doc.get("metadata", {})
            page_info = ""
            if metadata.get("page"):
                page_info = f" (Page {metadata['page']})"
            source = metadata.get("source") or metadata.get("title") or f"doc-{idx}"
            tags = metadata.get("tags", [])
            if isinstance(tags, str):
                try:
                    import json
                    parsed_tags = json.loads(tags)
                    if isinstance(parsed_tags, list):
                        tags = parsed_tags
                    else:
                        tags = [str(parsed_tags)]
                except Exception:
                    tags = [tags]
            if tags is None:
                tags = []
            elif not isinstance(tags, list):
                tags = [tags]
            formatted.append(
                {
                    "id": doc.get("id"),
                    "source": source + page_info,
                    "title": metadata.get("title"),
                    "page": metadata.get("page"),
                    "uploaded_at": metadata.get("uploaded_at"),
                    "tags": tags,
                    "snippet": doc.get("text", "")[:300],
                }
            )
        return formatted
