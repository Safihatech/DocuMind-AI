"""Hybrid search route: returns vector and keyword search results."""
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/search", tags=["search"]) 


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/hybrid")
async def hybrid_search(payload: SearchRequest, request: Request):
    vs = request.app.state.vector_store
    # vector part
    from app.core.embeddings import embed_texts

    embedding = embed_texts([payload.query])[0]
    vector_results = vs.query(embedding, top_k=payload.top_k)
    # keyword part
    keyword_results = vs.keyword_search(payload.query, top_k=payload.top_k)
    return {"query": payload.query, "vector": vector_results, "keyword": keyword_results}
