from app.agents.orchestrator import Orchestrator
from app.core.vector_store import VectorStore
from app.core.memory import ConversationMemory
from app.config import get_settings


def test_orchestrator_language_graph_pipeline():
    settings = get_settings()
    orchestrator = Orchestrator(
        vector_store=VectorStore(),
        embeddings_model=None,
        memory=ConversationMemory(),
        settings=settings,
    )

    result = orchestrator.handle_query("What is the main idea of this test?", top_k=3, use_hybrid=True)

    assert isinstance(result, dict)
    assert "answer" in result
    assert "citations" in result
    assert isinstance(result["citations"], list)
    assert result["answer"] != ""
    assert orchestrator.memory.get()
