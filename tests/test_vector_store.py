from app.core.vector_store import VectorStore


def test_vector_store_sanitize_metadatas_removes_none_values():
    raw_metadatas = [
        {"title": "Hello", "user_id": None, "tags": ["example"]},
        {"source": "upload", "page": 1, "uploaded_at": None},
    ]

    cleaned = VectorStore.sanitize_metadatas(raw_metadatas)

    assert cleaned == [
        {"title": "Hello", "tags": "[\"example\"]"},
        {"source": "upload", "page": 1},
    ]
