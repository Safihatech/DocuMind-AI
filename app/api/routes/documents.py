"""Routes for document ingestion and management."""
from pathlib import Path
import shutil
import requests
import logging
import uuid
import concurrent.futures
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, BackgroundTasks, status
from app.core.utils import ensure_dir
from app.core.embeddings import embed_texts
from app.models.schemas import DocumentInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

# Use an absolute upload directory rooted at the project workspace so uploads
# are always written to the expected uploads folder regardless of process cwd.
UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
ensure_dir(UPLOAD_DIR)


def get_optional_user(request: Request):
    user_id = request.headers.get('x-user-id')
    if user_id is None:
        return None
    try:
        user_id_int = int(user_id)
    except ValueError:
        return None
    return request.app.state.db.get_user_by_id(user_id_int)


def _run_with_timeout(func, *args, timeout=30, **kwargs):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=timeout)


def _process_and_index(app, save_path: str, document_id: int, user_id: int | None):
    """Background worker: process file, compute embeddings, and add documents to the vector store."""
    path = Path(save_path)
    print(f"[upload] Starting processing for document_id={document_id} path={save_path}")
    try:
        from app.agents.document_processor import DocumentProcessor
    except Exception as exc:
        logger.exception("DocumentProcessor import failed for %s: %s", save_path, exc)
        print(f"[upload] DocumentProcessor import failed: {exc}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        try:
            app.state.indexing_status[document_id] = {"status": "failed", "message": str(exc), "chunks": 0}
        except Exception:
            pass
        return

    processor = DocumentProcessor()
    try:
        print("[upload] 1 file received")
        print("[upload] 2 reading file content")
        print("[upload] 3 extracting text")
        docs = _run_with_timeout(processor.process, path, timeout=30)
        print("[upload] 4 splitting into paragraphs")
        print(f"[upload] Text extracted, {len(docs)} chunks prepared")
    except concurrent.futures.TimeoutError as exc:
        logger.exception("Document processing timed out for %s", save_path)
        print(f"[upload] Document processing timed out: {exc}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        try:
            app.state.indexing_status[document_id] = {"status": "failed", "message": "processing timed out", "chunks": 0}
        except Exception:
            pass
        return
    except Exception as exc:
        logger.exception("Document processing failed for %s: %s", save_path, exc)
        print(f"[upload] Document processing failed: {exc}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        try:
            app.state.indexing_status[document_id] = {"status": "failed", "message": str(exc), "chunks": 0}
        except Exception:
            pass
        return

    if not docs:
        logger.warning("No docs extracted from %s", save_path)
        print(f"[upload] No docs extracted from {save_path}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        return

    try:
        app.state.indexing_status[document_id] = {"status": "processing", "message": None, "chunks": None}
    except Exception:
        pass

    try:
        for idx, doc in enumerate(docs):
            text = doc.get("text", "")
            doc["id"] = f"{document_id}-{idx+1}"
            doc["metadata"] = doc.get("metadata", {})
            doc["metadata"]["user_id"] = user_id
            doc["metadata"]["source"] = doc["metadata"].get("source") or doc["metadata"].get("title")
            doc["metadata"]["document_id"] = document_id
            doc["metadata"]["uploaded_at"] = doc["metadata"].get("uploaded_at")

        print("[upload] 5 generating embeddings")
        chunks = [doc["text"] for doc in docs]
        embeddings = _run_with_timeout(embed_texts, chunks, timeout=30)
        print("[upload] 6 storing in chromadb")
        for idx, doc in enumerate(docs):
            emb = embeddings[idx]
            doc["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb

        app.state.vector_store.add_documents(docs)
        app.state.db.update_document_status(document_id, "indexed", chunks=len(docs))
        try:
            app.state.indexing_status[document_id] = {"status": "indexed", "message": None, "chunks": len(docs)}
        except Exception:
            pass
        logger.info("Indexed %d chunks from %s", len(docs), save_path)
        print(f"[upload] Stored in ChromaDB, upload complete for document_id={document_id}")
        print("[upload] 7 upload complete")
    except concurrent.futures.TimeoutError as exc:
        logger.exception("Embedding generation timed out for %s", save_path)
        print(f"[upload] Embedding generation timed out: {exc}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        try:
            app.state.indexing_status[document_id] = {"status": "failed", "message": "embedding timed out", "chunks": 0}
        except Exception:
            pass
    except Exception as exc:
        logger.exception("Embedding generation failed for %s", save_path)
        print(f"[upload] Embedding generation failed: {exc}")
        app.state.db.update_document_status(document_id, "failed", chunks=0)
        try:
            app.state.indexing_status[document_id] = {"status": "failed", "message": str(exc), "chunks": 0}
        except Exception:
            pass


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile | None = File(None),
    files: list[UploadFile] | None = File(None),
    background_tasks: BackgroundTasks = None,
):
    """Upload a document for ingestion and index it into ChromaDB (processing happens in background)."""
    user = get_optional_user(request)
    user_id = user["id"] if user else None

    uploaded_files: list[UploadFile] = []
    if files:
        uploaded_files.extend(files)
    if file:
        uploaded_files.append(file)

    if not uploaded_files:
        raise HTTPException(status_code=400, detail="No files provided.")

    settings = request.app.state.settings
    results = []

    for file in uploaded_files:
        filename = Path(file.filename).name
        if not filename:
            continue

        ext = Path(filename).suffix.lower()
        if ext not in {".pdf", ".txt", ".md", ".png", ".jpg", ".jpeg", ".bmp", ".tiff"}:
            results.append({"status": "error", "message": "Unsupported file type", "filename": filename})
            continue

        try:
            print(f"[upload] File received: {filename}")
            user_dir = UPLOAD_DIR / (str(user_id) if user_id is not None else "anonymous")
            user_dir.mkdir(parents=True, exist_ok=True)
            save_path = user_dir / filename
            if save_path.exists():
                save_path = user_dir / f"{uuid.uuid4().hex}_{filename}"

            with save_path.open("wb") as out_file:
                shutil.copyfileobj(file.file, out_file)
            print(f"[upload] Saved file to {save_path}")
        except Exception as exc:
            logger.exception("Failed to save uploaded file %s: %s", filename, exc)
            results.append({"status": "error", "message": "Failed to save file", "filename": filename})
            continue

        try:
            document_id = request.app.state.db.create_document(filename, str(save_path), user_id=user_id, status="queued")
        except Exception as exc:
            logger.exception("Failed to create document record for %s: %s", filename, exc)
            results.append({"status": "error", "message": "Failed to create document record", "filename": filename})
            continue

        try:
            request.app.state.indexing_status[document_id] = {"status": "queued", "message": None, "chunks": 0}
        except Exception:
            pass

        # Optionally call remote document processing MCP for immediate processing
        if settings.document_processing_api_url:
            try:
                with save_path.open('rb') as fp:
                    files_payload = {"file": (filename, fp, file.content_type)}
                    resp = requests.post(settings.document_processing_api_url.rstrip('/') + '/process', files=files_payload, timeout=30)
                if resp.status_code == 200:
                    logger.info("Document processing MCP returned success for %s", filename)
                    print(f"[upload] Remote document processor returned success for {filename}")
                else:
                    logger.warning(
                        "Document processing MCP returned status %s for %s; falling back to local processing.",
                        resp.status_code,
                        filename,
                    )
                    print(f"[upload] Remote document processor returned status {resp.status_code} for {filename}")
            except Exception as exc:
                logger.exception("Error calling document processing MCP; falling back to local processing for %s", filename)
                print(f"[upload] Remote processing call failed for {filename}: {exc}")

        try:
            request.app.state.db.update_document_status(document_id, "processing")
            request.app.state.indexing_status[document_id] = {"status": "processing", "message": None, "chunks": 0}
        except Exception:
            pass

        results.append({"status": "success", "message": "Document uploaded successfully", "filename": filename, "document_id": document_id})

    # schedule background processing for all uploaded files
    if background_tasks is not None:
        for file_entry in results:
            if file_entry.get("status") != "success":
                continue
            filename = file_entry["filename"]
            user_dir = UPLOAD_DIR / (str(user_id) if user_id is not None else "anonymous")
            save_path = user_dir / filename
            if not save_path.exists():
                # try to find a file that ends with the filename (handles UUID prefixes)
                candidate = None
                for p in user_dir.rglob("*"):
                    try:
                        if p.is_file() and p.name.lower().endswith(filename.lower()):
                            candidate = p
                            break
                    except Exception:
                        continue
                if candidate:
                    save_path = candidate
            background_tasks.add_task(_process_and_index, request.app, str(save_path), file_entry["document_id"], user_id)
            print(f"[upload] Background processing scheduled for document_id={file_entry['document_id']}")
        return {"status": "success", "message": "Document uploaded successfully", "files": results}

    # synchronous processing when background_tasks not provided
    for file_entry in results:
        if file_entry.get("status") != "success":
            continue
        filename = file_entry["filename"]
        user_dir = UPLOAD_DIR / (str(user_id) if user_id is not None else "anonymous")
        save_path = user_dir / filename
        if not save_path.exists():
            candidate = None
            for p in user_dir.rglob("*"):
                try:
                    if p.is_file() and p.name.lower().endswith(filename.lower()):
                        candidate = p
                        break
                except Exception:
                    continue
            if candidate:
                save_path = candidate
        _process_and_index(request.app, str(save_path), file_entry["document_id"], user_id)
    return {"status": "success", "message": "Document uploaded successfully", "files": results}


@router.get("/list", response_model=list[DocumentInfo])
async def list_documents(request: Request):
    user = get_optional_user(request)
    user_id = user["id"] if user else None
    documents = request.app.state.db.list_documents(user_id)
    return [DocumentInfo(**doc) for doc in documents]


@router.post("/reindex/{document_id}")
async def reindex_document(document_id: int, request: Request):
    """Force reindex a previously uploaded document into the in-memory vector store.

    This locates the file stored on disk (uses the DB `storage_path` if present,
    otherwise searches the `uploads/` directory for the filename) and processes
    it to add its chunks to the running `VectorStore` instance.
    """
    db = request.app.state.db
    vector_store = request.app.state.vector_store
    processor = None
    try:
        from app.agents.document_processor import DocumentProcessor
        from app.core.embeddings import embed_texts
        processor = DocumentProcessor()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document processor unavailable: {exc}")

    full = db.get_document(document_id)
    if not full:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = full.get("storage_path")
    filename = full.get("filename")
    candidate = None
    if storage_path and Path(storage_path).exists():
        candidate = Path(storage_path)
    else:
        # fallback: search uploads/ for matching filename
        uploads_root = Path(__file__).resolve().parents[3] / "uploads"
        for p in uploads_root.rglob(f"*{filename}"):
            candidate = p
            break

    if candidate is None or not candidate.exists():
        raise HTTPException(status_code=404, detail="Stored file not found on disk")

    try:
        chunks = processor.process(candidate)
        if not chunks:
            raise HTTPException(status_code=500, detail="No chunks extracted from file")
        texts = [c.get("text", "") for c in chunks]
        embs = embed_texts(texts)
        for i, c in enumerate(chunks):
            c["id"] = f"{document_id}-{i+1}"
            c["metadata"] = c.get("metadata", {})
            c["metadata"]["user_id"] = full.get("user_id")
            c["metadata"]["source"] = c["metadata"].get("source") or c["metadata"].get("title") or filename
            c["metadata"]["document_id"] = document_id
            c["embedding"] = embs[i].tolist() if hasattr(embs[i], "tolist") else embs[i]
        vector_store.add_documents(chunks)
        db.update_document_status(document_id, "indexed", chunks=len(chunks))
        return {"status": "ok", "message": "Document reindexed", "chunks": len(chunks)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Reindex failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status/{document_id}")
async def document_status(document_id: int, request: Request):
    user = get_optional_user(request)
    user_id = user["id"] if user else None
    settings = request.app.state.settings
    if getattr(settings, 'redis_url', None):
        try:
            import redis, json
            r = redis.from_url(settings.redis_url)
            val = r.get(f'index_status:{document_id}')
            if val:
                try:
                    parsed = json.loads(val)
                    return {"document_id": document_id, "status": parsed}
                except Exception:
                    return {"document_id": document_id, "status": val.decode() if isinstance(val, bytes) else val}
        except Exception:
            pass

    status_record = request.app.state.indexing_status.get(document_id)
    if not status_record:
        document = request.app.state.db.get_document(document_id, user_id=user_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found.")
        return {"document_id": document_id, "status": {"status": document.get("status", "unknown"), "chunks": document.get("chunks")}}

    return {"document_id": document_id, "status": status_record}
