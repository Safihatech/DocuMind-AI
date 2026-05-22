"""QA route that coordinates agents for question answering."""
import logging
from fastapi import APIRouter, Request
from app.models.schemas import QARequest, QAResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qa", tags=["qa"])


def get_optional_user_id(request: Request):
    user_id = request.headers.get('x-user-id')
    if user_id is None:
        return None
    try:
        return int(user_id)
    except ValueError:
        return None


@router.post("/query", response_model=QAResponse)
async def query_qa(payload: QARequest, request: Request):
    """Accept a user query and return an answer via the orchestrator."""
    user_id = get_optional_user_id(request)
    print(f"[qa] Query received: {payload.query} user_id={user_id} document_id={payload.document_id}")
    vector_store = request.app.state.vector_store
    print(f"[qa] Using vector_store id={id(vector_store)} collection={getattr(vector_store, 'collection_name', None)} api_url={getattr(vector_store, 'api_url', None)}")
    logger.info("Question received: %s", payload.query)
    orchestrator = request.app.state.orchestrator
    result = orchestrator.handle_query(
        payload.query,
        top_k=payload.top_k,
        use_hybrid=payload.use_hybrid,
        user_id=user_id,
        model=payload.model,
        document_id=payload.document_id,
    )
    sources = [c.get("source") for c in result.get("citations", []) if c.get("source")]
    logger.info("QA result ready; sources=%s", sources)
    print(f"[qa] Result answer length={len(result.get('answer', ''))} sources={sources}")
    return QAResponse(
        answer=result.get("answer", ""),
        citations=result.get("citations", []),
        sources=sources,
        follow_up=result.get("follow_up"),
        web_search=result.get("web_search", []),
    )
