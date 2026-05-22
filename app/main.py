"""FastAPI application entrypoint.

Initializes the FastAPI app, mounts static frontend, includes API routers,
and wires up basic startup/shutdown hooks to initialize shared components
like the embeddings model and vector store.

This is a lightweight, runnable implementation that uses the local
`VectorStore` and agent orchestrator stubs implemented in `app.agents`.
"""

from pathlib import Path
import logging
import shutil
import concurrent.futures

from fastapi import BackgroundTasks, File, FastAPI, HTTPException, Request, UploadFile
import uuid
from app.core.utils import ensure_dir
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from app.core.embeddings import embed_texts, get_gemini_client
from app.core.utils import chunk_text
from app.models.schemas import QARequest, QAResponse

from app.api.routes import agents as agents_router
from app.api.routes import auth as auth_router
from app.api.routes import documents as documents_router
from app.api.routes import history as history_router
from app.api.routes import qa as qa_router
from app.api.routes import search as search_router
from app.api.routes import user as user_router
from app.core.db import Database
from app.core.vector_store import VectorStore
from app.core.memory import ConversationMemory
from app.core.sql_memory import SQLiteConversationMemory
from app.agents.orchestrator import Orchestrator
from app.config import get_settings

logger = logging.getLogger(__name__)
GLOBAL_VECTOR_STORE = None
CHROMA_DB_DIR = Path(__file__).resolve().parents[1] / "chroma_db"


def _delete_local_chroma_db():
	try:
		if CHROMA_DB_DIR.exists():
			shutil.rmtree(CHROMA_DB_DIR)
			logger.info("Deleted existing local ChromaDB folder: %s", CHROMA_DB_DIR)
	except Exception as exc:
		logger.warning("Failed to delete chroma_db folder %s: %s", CHROMA_DB_DIR, exc)


class ResetVectorStore(VectorStore):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._collection_reset = False

	def begin_new_upload(self):
		self._collection_reset = False

	def _run_with_timeout(self, func, *args, timeout=30, **kwargs):
		with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
			future = executor.submit(func, *args, **kwargs)
			return future.result(timeout=timeout)

	def reset_collection(self):
		_delete_local_chroma_db()
		self._local_index = []
		self._collection_reset = True
		try:
			self._save_local_index()
		except Exception:
			pass

	def add_documents(self, docs):
		if docs and not self._collection_reset:
			logger.info("Resetting ChromaDB collection before upload. New document will replace old documents.")
			self.reset_collection()
		result = super().add_documents(docs)
		print(f"[upload] collection count after upload: {len(self._local_index)}")
		return result


async def _upload_document(request: Request, file: UploadFile | None = File(None), files: list[UploadFile] | None = File(None), background_tasks: BackgroundTasks = None):
	uploaded_files = []
	if files:
		uploaded_files.extend(files)
	if file:
		uploaded_files.append(file)
	if not uploaded_files:
		raise HTTPException(status_code=400, detail="No files provided.")

	vector_store = request.app.state.vector_store
	if hasattr(vector_store, "begin_new_upload"):
		vector_store.begin_new_upload()

	results = []
	for upload in uploaded_files:
		print("1 file received")
		# Save uploaded file to disk so background processors and status checks can locate it
		user = None
		try:
			user = request.headers.get('x-user-id')
		except Exception:
			user = None
		user_dir = Path(__file__).resolve().parents[1] / "uploads" / (str(user) if user is not None else "anonymous")
		ensure_dir(str(user_dir))
		filename = Path(upload.filename).name or f"upload_{uuid.uuid4().hex}.txt"
		save_path = user_dir / filename
		# Avoid overwriting existing file
		if save_path.exists():
			save_path = user_dir / f"{uuid.uuid4().hex}_{filename}"
		with save_path.open("wb") as out_file:
			# Read the full file content (no size limit here) and persist to disk.
			content_bytes = await upload.read()
			out_file.write(content_bytes)
		print("2 file saved to disk")
		try:
			text = content_bytes.decode("utf-8")
		except UnicodeDecodeError:
			text = content_bytes.decode("latin-1", errors="replace")
		print("3 extracting text")
		print("4 chunking text into semantic chunks")
		# Use the project's semantic chunking utility to produce small meaningful chunks
		full_text = text
		chunks = chunk_text(full_text, chunk_size=900, overlap=200)
		docs = []
		from datetime import datetime
		upload_time = datetime.utcnow().isoformat() + "Z"
		for idx, chunk in enumerate(chunks, start=1):
			docs.append({
				"id": f"{uuid.uuid4().hex}-{idx}",
				"text": chunk,
				"metadata": {
					"title": upload.filename,
					"source": upload.filename,
					"page": 1,
					"uploaded_at": upload_time,
					"tags": ["uploaded"],
				},
			})

		print("5 generating embeddings")
		chunks_texts = [doc["text"] for doc in docs]
		try:
			embeddings = concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(embed_texts, chunks_texts).result(timeout=30)
		except concurrent.futures.TimeoutError as exc:
			logger.exception("Embedding generation timed out for %s: %s", upload.filename, exc)
			return {"status": "error", "message": "Upload timed out during embedding generation"}
		except Exception as exc:
			logger.exception("Embedding generation failed for %s: %s", upload.filename, exc)
			return {"status": "error", "message": "Failed to generate embeddings"}

		for idx, doc in enumerate(docs):
			emb = embeddings[idx]
			doc["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb
			doc["metadata"]["chunk_index"] = idx

		print("6 storing in chromadb")
		try:
			# Add documents (with embeddings) to the vector store synchronously
			concurrent.futures.ThreadPoolExecutor(max_workers=1).submit(vector_store.add_documents, docs).result(timeout=30)
		except concurrent.futures.TimeoutError as exc:
			logger.exception("ChromaDB storage timed out for %s: %s", upload.filename, exc)
			return {"status": "error", "message": "Upload timed out during storage"}
		except Exception as exc:
			logger.exception("Failed to store documents for %s: %s", upload.filename, exc)
			results.append({"status": "error", "message": "Failed to store in vector store", "filename": upload.filename})
			continue

		print("7 upload complete")
		# Create a DB record for this upload so frontend can poll status.
		doc_id = None
		try:
			doc_id = request.app.state.db.create_document(filename, str(save_path), user_id=None, status="indexed")
			request.app.state.db.update_document_status(doc_id, "indexed", chunks=len(chunks))
		except Exception:
			doc_id = None
		try:
			request.app.state.indexing_status[doc_id] = {"status": "indexed", "message": None, "chunks": len(chunks)}
		except Exception:
			pass
		results.append({"status": "success", "filename": filename, "document_id": doc_id, "chunks": len(chunks)})

	return {"status": "success", "message": "Document uploaded successfully", "files": results}


async def _query_qa(payload: QARequest, request: Request):
	query = payload.query or ""
	if not query.strip():
		raise HTTPException(status_code=400, detail="Query text is required.")

	vector_store = request.app.state.vector_store
	try:
		embedding = embed_texts([query])[0]
	except Exception as exc:
		logger.exception("Embedding generation failed for QA query: %s", exc)
		raise HTTPException(status_code=500, detail="Failed to generate embeddings for query.")

	results = vector_store.query(embedding, top_k=5)
	paragraphs = [item.get("text", "") for item in results if item.get("text")]
	context = "\n\n".join(paragraphs)
	print(f"[chat] joined context length={len(context)}")

	system_prompt = (
		"You are a document assistant. Answer the user question using only the context given. "
		"Be specific. Do not summarize unless asked. Do not use your own knowledge."
	)

	# Attempt LLM generation via Groq; use configured model with payload override.
	try:
		from groq import Groq
		model_name = payload.model or request.app.state.settings.groq_model or "mistral-saba-24b"
		if model_name in ('meta-llama-8b', 'mixtral-8x7b-32768') and request.app.state.settings.groq_model and request.app.state.settings.groq_model not in ('meta-llama-8b', 'mixtral-8x7b-32768'):
			logger.warning("Overriding unsupported model %s with configured GROQ_MODEL=%s", model_name, request.app.state.settings.groq_model)
			model_name = request.app.state.settings.groq_model
		client = Groq(api_key=request.app.state.settings.groq_api_key)
		response = client.chat.completions.create(
			model=model_name,
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"},
			],
			max_tokens=1024,
			temperature=0.2,
		)
		answer = response.choices[0].message.content.strip()
		# If the model returned an empty answer, treat it like a failure and fallback.
		if not answer:
			raise ValueError("Empty answer from Groq model")
	except Exception as exc:
		logger.exception("Groq generation failed: %s", exc)
		error_text = str(exc).lower()
		if 'decommissioned' in error_text and model_name != 'llama-3.3-70b-versatile':
			logger.warning("Retrying Groq with fallback model llama-3.3-70b-versatile")
			try:
				client = Groq(api_key=request.app.state.settings.groq_api_key)
				response = client.chat.completions.create(
					model='llama-3.3-70b-versatile',
					messages=[
						{"role": "system", "content": system_prompt},
						{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"},
					],
					max_tokens=1024,
					temperature=0.2,
				)
				answer = response.choices[0].message.content.strip()
				if answer:
					return QAResponse(
						answer=answer,
						citations=[],
						sources=[],
						follow_up=None,
						web_search=[],
					)
			except Exception as exc2:
				logger.exception("Groq fallback generation failed: %s", exc2)
		# Provide a helpful fallback: return retrieved context if available, plus an error note.
		if context:
			snippet = context[:4000] if len(context) > 4000 else context
			answer = (
				"[Generation failed: " + str(exc) + "]\n\n" +
				"Retrieved context (used for answer):\n" + snippet
			)
		else:
			answer = f"Generation failed: {exc}. Check GROQ_API_KEY and model access."

	return QAResponse(
		answer=answer,
		citations=[],
		sources=[],
		follow_up=None,
		web_search=[],
	)


def create_app() -> FastAPI:
	settings = get_settings()
	app = FastAPI(title=settings.app_name, debug=settings.debug)

	# Include API routers first (so they take precedence over static mount)
	app.include_router(auth_router.router)
	app.include_router(agents_router.router)
	app.include_router(documents_router.router)
	app.include_router(history_router.router)
	app.include_router(qa_router.router)
	app.include_router(search_router.router)
	app.include_router(user_router.router)

	# Use the router-defined document upload and QA endpoints from app/api/routes.
	# This ensures uploads are processed with DocumentProcessor and QA uses Orchestrator.

	# Define the health check endpoint
	@app.get("/health")
	async def health():
		return {"status": "ok"}

	@app.get("/test")
	async def test_status():
		return {"status": "ok", "message": "Backend is working"}

	@app.get("/test-chromadb")
	async def test_chromadb():
		try:
			count = len(getattr(app.state.vector_store, "_local_index", []))
			return {"ok": True, "indexed_documents": count}
		except Exception as exc:
			logger.exception("ChromaDB test failed")
			return {"ok": False, "error": str(exc)}

	@app.get("/test-groq")
	async def test_groq():
		key = getattr(settings, "groq_api_key", None)
		if not key:
			return {"ok": False, "error": "GROQ_API_KEY not configured"}
		try:
			from groq import Groq
			Groq(api_key=key)
			return {"ok": True, "message": "Groq API key is configured"}
		except Exception as exc:
			logger.exception("Groq test failed")
			return {"ok": False, "error": str(exc)}

	# Redirect root to the frontend static app
	@app.get("/")
	async def root():
		return RedirectResponse(url="/static/")

	# Application state for shared components
	@app.on_event("startup")
	async def startup_event():
		global GLOBAL_VECTOR_STORE
		app.state.settings = settings
		logger.info("GROQ API key configured: %s", bool(settings.groq_api_key))
		if not settings.groq_api_key:
			logger.warning("GROQ_API_KEY is missing. Groq answer generation will fall back to retrieved document context only.")
		# Preload the embedding client once during startup so the upload path
		# does not pay the initialization cost on first processing.
		app.state.embeddings_model = get_gemini_client()
		logger.info("Embedding model preloaded at startup: %s", bool(app.state.embeddings_model))
		_delete_local_chroma_db()
		GLOBAL_VECTOR_STORE = ResetVectorStore(api_url=settings.chroma_api_url, collection_name="documents")
		app.state.vector_store = GLOBAL_VECTOR_STORE
		logger.info("Global ChromaDB vector store initialized: id=%s collection=%s api_url=%s",
			id(app.state.vector_store), app.state.vector_store.collection_name, app.state.vector_store.api_url)
		# Track background indexing status for uploads: { document_id: {status, message, chunks} }
		app.state.indexing_status = {}
		app.state.db = Database(db_path=settings.database_path)
		# Choose persistent SQLite memory if configured, otherwise use in-memory buffer
		if settings.use_sqlite_memory:
			app.state.memory = SQLiteConversationMemory(db_path=settings.sqlite_db_path)
		else:
			app.state.memory = ConversationMemory()
		app.state.orchestrator = Orchestrator(
			vector_store=app.state.vector_store,
			embeddings_model=app.state.embeddings_model,
			memory=app.state.memory,
			db=app.state.db,
			settings=settings,
		)

		# Re-indexing previously indexed documents on startup is disabled.
		# Documents are uploaded and indexed at runtime only, so stale storage
		# paths should not produce unnecessary warnings during startup.

	@app.on_event("shutdown")
	async def shutdown_event():
		# Cleanup resources if needed
		try:
			if settings.use_sqlite_memory and hasattr(app.state.memory, "close"):
				app.state.memory.close()
		except Exception:
			pass

	# Mount frontend static files last at /static/ (so routers take precedence)
	static_dir = Path(__file__).resolve().parent.parent / "frontend"
	app.mount("/static", StaticFiles(directory=str(static_dir), html=True), name="frontend")

	return app


app = create_app()


if __name__ == "__main__":
	uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
