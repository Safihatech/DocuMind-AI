"""Celery application and background tasks for document processing.

This module defines a Celery instance configured via the `REDIS_URL`
environment variable (or defaults to `redis://redis:6379/0`) and exposes
the `process_document_task` task which performs document processing,
embeddings, and indexing into the configured `VectorStore`.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from celery import Celery

try:
    import redis
except Exception:
    redis = None

from app.agents.document_processor import DocumentProcessor
from app.core.embeddings import embed_texts
from app.core.vector_store import VectorStore


REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')


def _make_celery(broker_url: str):
    return Celery('app', broker=broker_url, backend=broker_url)


celery_app = _make_celery(REDIS_URL)


def _redis_client():
    if redis is None:
        return None
    return redis.from_url(REDIS_URL)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def process_document_task(self, filepath: str, document_id: int):
    """Process a document file and index its chunks into the vector store.

    The task writes status updates into Redis under key `index_status:{document_id}`
    as a JSON-encoded object so the API can report progress.
    """
    r = _redis_client()
    try:
        if r is not None:
            r.set(f'index_status:{document_id}', json.dumps({'status': 'processing', 'message': None, 'chunks': 0}))

        processor = DocumentProcessor()
        docs = processor.process(Path(filepath))

        if not docs:
            if r is not None:
                r.set(f'index_status:{document_id}', json.dumps({'status': 'failed', 'message': 'no_docs', 'chunks': 0}))
            return {'status': 'failed', 'message': 'no_docs'}

        chunks = [d['text'] for d in docs]
        embeddings = embed_texts(chunks)

        for idx, doc in enumerate(docs):
            emb = embeddings[idx]
            doc['embedding'] = emb.tolist() if hasattr(emb, 'tolist') else emb

        vs = VectorStore(api_url=os.getenv('CHROMA_API_URL') or None)
        vs.add_documents(docs)

        if r is not None:
            r.set(f'index_status:{document_id}', json.dumps({'status': 'indexed', 'message': None, 'chunks': len(docs)}))
        return {'status': 'indexed', 'chunks': len(docs)}
    except Exception as exc:  # pragma: no cover - best-effort retry logic
        if r is not None:
            try:
                r.set(f'index_status:{document_id}', json.dumps({'status': 'failed', 'message': str(exc), 'chunks': 0}))
            except Exception:
                pass
        try:
            self.retry(exc=exc)
        except Exception:
            raise
