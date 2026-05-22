"""Agent-related API endpoints (for orchestration/testing)."""
from fastapi import APIRouter, Request

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status")
async def agents_status(request: Request):
    memory = request.app.state.memory
    vector_store = request.app.state.vector_store
    memory_items = []
    try:
        memory_items = memory.get() if memory else []
    except Exception:
        memory_items = []

    vector_count = 0
    try:
        vector_count = len(getattr(vector_store, "_local_index", []))
    except Exception:
        vector_count = 0

    return {
        "status": "OK",
        "memory_count": len(memory_items),
        "indexed_documents": vector_count,
        "groq_enabled": bool(getattr(request.app.state.settings, "groq_api_key", None)),
        "web_search_configured": bool(getattr(request.app.state.settings, "web_search_api_url", None)),
        "document_processing_configured": bool(getattr(request.app.state.settings, "document_processing_api_url", None)),
    }


@router.get("/memory")
async def memory_state(request: Request):
    memory = request.app.state.memory
    return {"conversation_memory": memory.get() if memory else []}
