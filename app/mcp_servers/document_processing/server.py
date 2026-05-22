"""MCP wrapper for document processing.

This server exposes a simple process endpoint that can extract text and metadata
from supported files. It is optional but useful when separating ingestion from
query-time application logic.
"""
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File
from app.agents.document_processor import DocumentProcessor

app = FastAPI()
processor = DocumentProcessor()


@app.get("/ping")
async def ping():
    return {"status": "ok"}


@app.post("/process")
async def process_document(file: UploadFile = File(...)):
    filename = Path(file.filename).name
    if not filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    temp_path = Path("uploads") / filename
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    with temp_path.open("wb") as out_file:
        out_file.write(await file.read())

    try:
        docs = processor.process(temp_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not docs:
        raise HTTPException(status_code=400, detail="No extractable content found.")

    return {"filename": filename, "chunks": len(docs), "documents": docs}
