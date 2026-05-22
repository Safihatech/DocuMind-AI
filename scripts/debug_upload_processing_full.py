from pathlib import Path
import traceback

from app.agents.document_processor import DocumentProcessor
from app.core.embeddings import embed_texts
from app.core.vector_store import VectorStore

try:
    file_path = Path('uploads/anonymous/research paper txt.txt')
    print('file_path:', file_path)
    print('exists:', file_path.exists())

    proc = DocumentProcessor()
    docs = proc.process(file_path)
    print('docs count:', len(docs))
    if docs:
        print('first id:', docs[0]['id'])
        print('first text length:', len(docs[0]['text']))

    embs = embed_texts([d['text'] for d in docs[:3]])
    print('embeddings count:', len(embs), 'dim:', len(embs[0]) if embs else None)

    vs = VectorStore()
    emb0 = embed_texts([docs[0]['text']])[0]
    print('emb0 dim', len(emb0))
    vs.add_documents([
        {'id': 'test-1', 'text': docs[0]['text'], 'metadata': docs[0]['metadata'], 'embedding': emb0}
    ])
    print('added local index:', len(vs._local_index))
    res = vs.query(emb0, top_k=1)
    print('query result length:', len(res))
    print('query result sample:', res[:1])
except Exception:
    traceback.print_exc()
    raise
