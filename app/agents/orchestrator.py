"""Orchestrator agent: coordinates other agents to answer queries.

Uses `langgraph` to orchestrate a multi-agent pipeline for query analysis,
retrieval, reranking, citation formatting, and answer generation.
"""
from typing import Any, Dict, List, TypedDict
import logging

from langgraph.graph import StateGraph

from app.agents.query_analyzer import QueryAnalyzer
from app.agents.retrieval import RetrievalAgent
from app.agents.reranker import Reranker
from app.agents.generator import Generator
from app.agents.citation import CitationAgent

logger = logging.getLogger(__name__)


class OrchestratorState(TypedDict, total=False):
    query: str
    top_k: int
    use_hybrid: bool
    user_id: int
    document_id: int
    model: str
    analysis: Dict[str, Any]
    documents: List[Dict[str, Any]]
    web_results: List[Dict[str, Any]]
    reranked: List[Dict[str, Any]]
    answer: str
    citations: List[Dict[str, Any]]


class Orchestrator:
    def __init__(self, vector_store, embeddings_model, memory=None, db=None, settings=None):
        self.vector_store = vector_store
        self.embeddings_model = embeddings_model
        self.memory = memory
        self.db = db
        self.settings = settings
        self.query_analyzer = QueryAnalyzer()
        self.retrieval_agent = RetrievalAgent(
            vector_store,
            embeddings_model,
            web_search_url=settings.web_search_api_url if settings else None,
        )
        self.reranker = Reranker()
        self.generator = Generator(api_key=settings.groq_api_key if settings else None)
        self.citation_agent = CitationAgent()
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(
            state_schema=OrchestratorState,
            input_schema=OrchestratorState,
            output_schema=OrchestratorState,
        )
        graph.add_sequence(
            [
                ("analyze", self._analyze),
                ("retrieve", self._retrieve),
                ("rerank", self._rerank),
                ("generate", self._generate),
                ("cite", self._cite),
                ("store_memory", self._store_memory),
            ]
        )
        graph.set_entry_point("analyze").set_finish_point("store_memory")
        return graph.compile()

    def _analyze(self, state: OrchestratorState) -> OrchestratorState:
        query = state.get("query", "")
        analysis = self.query_analyzer.analyze(query)
        return {"analysis": analysis}

    def _retrieve(self, state: OrchestratorState) -> OrchestratorState:
        query = state.get("query", "")
        logger.info("Searching ChromaDB for query: %s", query)
        try:
            print("Collection count:", self.vector_store.count())
        except Exception as exc:
            print("Collection count error:", exc)
        top_k = state.get("top_k", 5)
        use_hybrid = state.get("use_hybrid", True)
        use_web = state.get("analysis", {}).get("use_web_search", False)
        user_id = state.get("user_id")
        document_id = state.get("document_id")
        retrieval_results = self.retrieval_agent.retrieve(
            query,
            top_k=top_k,
            use_hybrid=use_hybrid,
            use_web=use_web,
            user_id=user_id,
            document_id=document_id,
        )
        print("Query results:", retrieval_results.get("documents"))
        return {
            "documents": retrieval_results.get("documents", []),
            "web_results": retrieval_results.get("web_results", []),
        }

    def _rerank(self, state: OrchestratorState) -> OrchestratorState:
        query = state.get("query", "")
        documents = state.get("documents", [])
        reranked = self.reranker.rerank(query, documents)
        return {"reranked": reranked}

    def _generate(self, state: OrchestratorState) -> OrchestratorState:
        query = state.get("query", "")
        reranked = state.get("reranked", [])
        web_results = state.get("web_results", [])
        logger.info("Sending query to generator: %s", query)
        memory_context = None
        user_id = state.get("user_id")
        # prefer explicit model in state; if None, use configured `groq_model`
        model = state.get("model") or (self.settings.groq_model if self.settings else None)
        if model in ('meta-llama-8b', 'mixtral-8x7b-32768') and self.settings and self.settings.groq_model and self.settings.groq_model not in ('meta-llama-8b', 'mixtral-8x7b-32768'):
            logger.warning("Overriding unsupported explicit model %s with configured GROQ_MODEL=%s", model, self.settings.groq_model)
            model = self.settings.groq_model
        if self.db is not None:
            try:
                memory_context = self.db.get_recent_conversation(limit=5)
            except TypeError:
                # fallback if DB has older signature
                memory_context = None
        elif self.memory is not None:
            memory_context = self.memory.get() if hasattr(self.memory, "get") else None
        answer = self.generator.generate(
            query,
            reranked,
            model=model,
            memory=memory_context,
            web_results=web_results,
        )
        return {"answer": answer}

    def _cite(self, state: OrchestratorState) -> OrchestratorState:
        reranked = state.get("reranked", [])
        citations = self.citation_agent.format(reranked)
        return {"citations": citations}

    def _store_memory(self, state: OrchestratorState) -> OrchestratorState:
        query = state.get("query")
        answer = state.get("answer")
        user_id = state.get("user_id")
        if self.db is not None and query and answer:
            self.db.create_chat(query, answer, user_id)
        elif self.memory is not None and query and answer:
            self.memory.add(user=query, bot=answer)
        return {}

    def handle_query(self, query: str, top_k: int = 5, use_hybrid: bool = True, user_id: int | None = None, document_id: int | None = None, model: str | None = None) -> Dict:
        """Handle a user query through the full RAG pipeline."""
        try:
            inputs: OrchestratorState = {
                "query": query,
                "top_k": top_k,
                "use_hybrid": use_hybrid,
                "user_id": user_id,
                "document_id": document_id,
                "model": model,
            }
            output_state = self.graph.invoke(inputs)

            answer = output_state.get("answer", "")
            citations = output_state.get("citations", [])
            web_results = output_state.get("web_results", [])

            result = {
                "answer": answer,
                "citations": citations,
                "follow_up": "Would you like to refine this answer or ask a follow-up question?",
            }
            if web_results:
                result["web_search"] = web_results
            return result
        except Exception as e:
            logger.error(f"Error in orchestrator: {e}")
            return {
                "answer": f"Error processing your query: {str(e)}",
                "citations": [],
                "follow_up": None,
            }
