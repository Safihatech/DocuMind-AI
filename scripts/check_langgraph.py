from app.agents.orchestrator import Orchestrator
from app.core.vector_store import VectorStore
from app.core.memory import ConversationMemory
from app.config import get_settings

settings = get_settings()
orchestrator = Orchestrator(VectorStore(), None, memory=ConversationMemory(), settings=settings)
result = orchestrator.handle_query('What is the status of the uploaded documents?', top_k=2, use_hybrid=True)
print(list(result.keys()))
print(result['answer'][:120])
print(len(result['citations']))
print(len(orchestrator.memory.get()))
