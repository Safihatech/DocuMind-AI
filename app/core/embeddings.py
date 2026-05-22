
"""Embeddings helper using Gemini API.

Uses Gemini embeddings as the primary method. Falls back to a deterministic
hash-based embedding only when Gemini is unavailable or fails.
"""

import logging
import os
from typing import List

from app.config import get_settings

_gemini_client = None
_gemini_client_is_new = False


def get_gemini_client():
    """Return a Gemini embedding client or model object, or None on failure."""
    global _gemini_client, _gemini_client_is_new
    if _gemini_client is None:
        api_key = os.getenv("GEMINI_API_KEY") or get_settings().gemini_api_key
        if not api_key:
            return None
        try:
            from google import genai

            _gemini_client = genai.Client(api_key=api_key)
            _gemini_client_is_new = True
        except Exception as exc:
            logging.info("google-genai unavailable, falling back to google.generativeai: %s", exc)
            try:
                import google.generativeai as genai

                genai.configure(api_key=api_key)
                _gemini_client = genai.get_model("models/embedding-001")
                _gemini_client_is_new = False
            except Exception as exc2:
                logging.warning("Could not initialize Gemini embedding client: %s", exc2)
                _gemini_client = None
    return _gemini_client


def _fallback_encode(texts: list, dim: int = 128):
    """Deterministic lightweight fallback embedding using SHA256 hashing.

    Produces a fixed-size float vector for each input text. This is
    suitable for development and testing when sentence-transformers is
    unavailable, but should be replaced by a proper model for production.
    """
    import hashlib

    vectors = []
    for t in texts:
        h = hashlib.sha256(t.encode('utf-8')).digest()
        # Expand/chunk the digest to `dim` floats by repeating if needed
        vals = []
        i = 0
        while len(vals) < dim:
            byte = h[i % len(h)]
            vals.append((byte / 255.0) * 2.0 - 1.0)  # map to [-1, 1]
            i += 1
        # Normalize
        norm = sum(x * x for x in vals) ** 0.5 or 1.0
        vectors.append([x / norm for x in vals])
    return vectors


def embed_texts(texts: list):
    """Encode `texts` into embeddings using Gemini API, with fallback to hash embeddings."""
    texts = [str(t) for t in texts if t is not None]
    if not texts:
        return []
    # Try to use Gemini with a small retry/backoff loop for transient errors (e.g., 429).
    client = get_gemini_client()
    if client is not None:
        import time

        attempts = 3
        backoff = 1.0
        for attempt in range(1, attempts + 1):
            try:
                if _gemini_client_is_new and hasattr(client, "models"):
                    response = client.models.embed_content(
                        model="gemini-embedding-001",
                        contents=texts,
                    )
                    embeddings = getattr(response, "embeddings", None)
                    if embeddings is not None:
                        return [
                            getattr(item, "values", item.get("values") if isinstance(item, dict) else None)
                            for item in embeddings
                        ]
                else:
                    result = client.embed_content(texts)
                    if isinstance(result, dict) and "embeddings" in result:
                        return [e["values"] for e in result["embeddings"]]
                    if isinstance(result, list) and all(isinstance(e, dict) and "values" in e for e in result):
                        return [e["values"] for e in result]
                    if isinstance(result, dict) and "values" in result:
                        return [result["values"]]
                    return result
            except Exception as e:
                logging.warning("Error using Gemini embedding model (attempt %d/%d): %s", attempt, attempts, e)
                # If this was the last attempt, break and fall back.
                if attempt >= attempts:
                    break
                # Exponential backoff before retrying
                try:
                    time.sleep(backoff)
                except Exception:
                    pass
                backoff *= 2

    logging.warning("Falling back to deterministic embedding fallback")
    return _fallback_encode(texts)
