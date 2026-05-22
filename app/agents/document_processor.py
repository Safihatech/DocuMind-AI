"""Document processing agent for ingestion and metadata preservation."""
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from app.core.utils import chunk_text

SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md"}
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
SUPPORTED_PDF_EXTENSIONS = {".pdf"}


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class DocumentProcessor:
    def __init__(self, chunk_size: int = 900, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def process(self, path: Path) -> List[Dict]:
        ext = path.suffix.lower()
        if ext in SUPPORTED_PDF_EXTENSIONS:
            try:
                from app.core.pdf_processing import extract_text_from_pdf
            except Exception as exc:
                raise RuntimeError(
                    "PDF processing support is unavailable. Install PyMuPDF and its dependencies."
                ) from exc
            pages = extract_text_from_pdf(str(path))
        elif ext in SUPPORTED_IMAGE_EXTENSIONS:
            try:
                from app.core.ocr import ocr_image
            except Exception as exc:
                raise RuntimeError(
                    "Image OCR support is unavailable. Install pillow and pytesseract."
                ) from exc
            pages = [ocr_image(str(path))]
        elif ext in SUPPORTED_TEXT_EXTENSIONS:
            pages = [_read_text_file(path)]
        else:
            raise ValueError(f"Unsupported file type: {ext}")

        docs = []
        upload_time = datetime.utcnow().isoformat() + "Z"
        chunk_id = 1
        for page_num, page_text in enumerate(pages, start=1):
            if not page_text or not page_text.strip():
                continue
            chunks = chunk_text(page_text, chunk_size=self.chunk_size, overlap=self.overlap)
            for chunk in chunks:
                docs.append(
                    {
                        "id": f"{path.name}-{page_num}-{chunk_id}",
                        "text": chunk,
                        "metadata": {
                            "title": path.name,
                            "source": str(path),
                            "page": page_num,
                            "uploaded_at": upload_time,
                            "tags": ["uploaded"],
                        },
                    }
                )
                chunk_id += 1
        return docs
