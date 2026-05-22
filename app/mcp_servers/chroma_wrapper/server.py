"""MCP wrapper for ChromaDB vector database."""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import chromadb

app = FastAPI()
client = chromadb.Client()
collection = client.get_or_create_collection(name="documents")


class AddRequest(BaseModel):
    collection_name: str | None = None
    ids: List[str]
    texts: List[str]
    metadatas: List[Dict[str, Any]]
    embeddings: List[List[float]] | None = None


class QueryRequest(BaseModel):
    collection_name: str | None = None
    embedding: List[float]
    top_k: int = 5


@app.get("/ping")
async def ping():
    return {"status": "ok"}


@app.post("/add")
async def add_documents(payload: AddRequest):
    target_collection = client.get_or_create_collection(name=payload.collection_name or "documents")
    if payload.embeddings:
        target_collection.add(ids=payload.ids, documents=payload.texts, metadatas=payload.metadatas, embeddings=payload.embeddings)
    else:
        target_collection.add(ids=payload.ids, documents=payload.texts, metadatas=payload.metadatas)
    return {"added": len(payload.ids)}


@app.post("/query")
async def query_vectors(payload: QueryRequest):
    target_collection = client.get_or_create_collection(name=payload.collection_name or "documents")
    result = target_collection.query(
        query_embeddings=[payload.embedding],
        n_results=payload.top_k,
        include=["documents", "metadatas", "distances", "ids"],
    )
    return result
