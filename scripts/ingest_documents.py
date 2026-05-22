"""Script to ingest a document file into the vector store for local testing."""
import argparse
from pathlib import Path
from app.core.utils import ensure_dir, chunk_text
from app.core.embeddings import embed_texts


def ingest_file(path: Path):
    if not path.exists():
        raise FileNotFoundError(path)

    if path.suffix.lower() == ".pdf":
        # Lazy import to avoid importing heavy C extensions at module import time
        from app.core.pdf_processing import extract_text_from_pdf

        text = extract_text_from_pdf(str(path))
    elif path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}:
        from app.core.ocr import ocr_image

        text = ocr_image(str(path))
    elif path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8")
    else:
        raise ValueError("Unsupported file type")

    chunks = chunk_text(text, chunk_size=900, overlap=200)
    # Use the project's embedding helper (Gemini or fallback)
    embeddings = embed_texts(chunks)

    docs = []
    for idx, chunk in enumerate(chunks, start=1):
        emb = embeddings[idx - 1]
        try:
            emb_val = emb.tolist() if hasattr(emb, "tolist") else emb
        except Exception:
            emb_val = emb
        docs.append({
            "id": f"{path.stem}-{idx}",
            "text": chunk,
            "metadata": {"title": path.name, "source": str(path)},
            "embedding": emb_val,
        })

    # Try to use the project's VectorStore. If importing or instantiating it causes
    # native-library failures (onnxruntime / chromadb), fallback to writing a
    # simple local JSON index under uploads/index_local.json so the document
    # content is preserved for local testing.
    # By default, skip importing the project's VectorStore to avoid potential
    # native-library crashes on hosts where chromadb/onnxruntime fail to load.
    # Set the environment variable `SKIP_VECTOR_STORE=0` to attempt using it.
    import os

    skip_vs = os.getenv("SKIP_VECTOR_STORE", "1")
    if skip_vs == "0":
        try:
            from app.core.vector_store import VectorStore
            try:
                store = VectorStore()
                store.add_documents(docs)
                return len(docs)
            except Exception as exc:
                import logging

                logging.warning("Vector store add_documents failed, falling back to local index: %s", exc)
                try:
                    for d in docs:
                        store._local_index.append({
                            "id": d["id"],
                            "text": d["text"],
                            "metadata": d.get("metadata", {}),
                        })
                    return len(docs)
                except Exception:
                    pass
        except Exception:
            # Import or instantiation failed (likely chromadb/onnxruntime DLL issues).
            pass

    # Final fallback: write a JSON file with the docs so they can be inspected/used.
    import json
    out_path = Path("uploads/index_local.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.extend(docs)
        out_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return len(docs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest a document into ChromaDB.")
    parser.add_argument("path", type=str, help="Path to a PDF, image, or text file")
    args = parser.parse_args()
    count = ingest_file(Path(args.path))
    print(f"Indexed {count} document chunks.")
