"""Utility helpers."""
import os
import re
from typing import List


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _split_sentences(paragraph: str) -> List[str]:
    # Very small sentence splitter based on punctuation.
    sentences = re.split(r'(?<=[.!?])\s+', paragraph.strip())
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Semantic chunking that preserves paragraph/sentence boundaries.

    Strategy:
    - Split the document into paragraphs (double newlines).
    - Split paragraphs into sentences.
    - Accumulate sentences into chunks trying not to break sentences and
      keeping chunks near `chunk_size`. Overlap controls repeated context.
    """
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = []
    current_len = 0

    for para in paragraphs:
        sentences = _split_sentences(para)
        if not sentences:
            sentences = [para]

        for sent in sentences:
            s_len = len(sent)
            # If adding this sentence would exceed chunk_size and current has content,
            # finalize the current chunk.
            if current and current_len + s_len > chunk_size:
                chunk_text = " ".join(current).strip()
                chunks.append(chunk_text)
                # create overlap by taking last `overlap` chars worth of words
                overlap_text = (chunk_text[-overlap:]) if overlap and len(chunk_text) > overlap else chunk_text
                current = [overlap_text] if overlap_text else []
                current_len = sum(len(x) for x in current)

            current.append(sent)
            current_len += s_len + 1

    if current:
        chunks.append(" ".join(current).strip())

    # Trim and return
    return [c for c in chunks if c]
