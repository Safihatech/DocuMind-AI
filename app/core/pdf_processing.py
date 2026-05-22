"""PDF processing utilities using PyMuPDF (fitz) with optional OCR for images.

This module extracts textual content per page and also attempts to OCR
embedded images on each page, appending their text to the page body. The
implementation aims to be robust for common PDFs and usable in development
without external services.
"""
from io import BytesIO


def _ocr_image_bytes(img_bytes: bytes) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception:
        return ""

    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        return pytesseract.image_to_string(img)
    except Exception:
        return ""
    try:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        return pytesseract.image_to_string(img)
    except Exception:
        return ""


def extract_text_from_pdf(path: str) -> list:
    """Return a list of strings, one per PDF page, combining page text
    and OCRed text from images found on the page.
    """
    try:
        import fitz
    except Exception as exc:
        raise RuntimeError(
            "PyMuPDF (fitz) is required for PDF processing. Install it to process PDFs."
        ) from exc

    doc = fitz.open(path)
    pages = []
    for page in doc:
        page_text = page.get_text() or ""
        # extract images on the page and OCR them
        img_texts = []
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            try:
                img_dict = doc.extract_image(xref)
                img_bytes = img_dict.get("image")
                if img_bytes:
                    t = _ocr_image_bytes(img_bytes)
                    if t:
                        img_texts.append(t)
            except Exception:
                continue

        combined = page_text
        if img_texts:
            combined = combined + "\n\n" + "\n\n".join(img_texts)
        pages.append(combined.strip())
    return pages
