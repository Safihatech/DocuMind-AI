from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(dotenv_path=Path('.env'))
print('GROQ_API_KEY', bool(os.getenv('GROQ_API_KEY')))
print('GEMINI_API_KEY', bool(os.getenv('GEMINI_API_KEY')))
print('CHROMA_API_URL', os.getenv('CHROMA_API_URL'))

from app.agents.document_processor import DocumentProcessor
from app.core.embeddings import embed_texts
from app.core.vector_store import VectorStore

path = Path('uploads/anonymous/f0749764dbc24170b41714774b440993_research paper txt.txt')
print('path exists', path.exists())
if not path.exists():
    raise SystemExit('Sample file not found')

proc = DocumentProcessor()
docs = proc.process(path)
print('processed chunk count', len(docs))
for i, d in enumerate(docs[:3], 1):
    print(f'chunk {i} len', len(d['text']))

embs = embed_texts([d['text'] for d in docs[:3]])
print('embeddings returned', len(embs))
print('first embedding length', len(embs[0]) if embs else None)

vs = VectorStore(api_url=os.getenv('CHROMA_API_URL'))
vs.add_documents(docs[:3])
print('local index count', len(vs._local_index))
print('collection present', hasattr(vs, 'collection') and vs.collection is not None)
