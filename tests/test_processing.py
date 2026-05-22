from app.core.utils import chunk_text


def test_chunking_smoke():
    text = """
    This is the first paragraph. It has several sentences. Here is another sentence.

    This is the second paragraph. It also has sentences. The chunker should keep sentences intact.
    """
    chunks = chunk_text(text, chunk_size=80, overlap=20)
    assert isinstance(chunks, list)
    assert len(chunks) >= 1
    for c in chunks:
        assert len(c) <= 200  # reasonably bounded
