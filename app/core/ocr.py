"""OCR helper using pytesseract and PIL."""
def ocr_image(image_path: str) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception as exc:
        raise RuntimeError(
            "OCR support requires pillow and pytesseract. Install them to process images."
        ) from exc

    img = Image.open(image_path)
    return pytesseract.image_to_string(img)
