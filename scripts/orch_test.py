import sys
sys.path.insert(0, '.')
from app.core.db import Database
from app.core.vector_store import VectorStore
from app.agents.orchestrator import Orchestrator
from app.config import get_settings

settings = get_settings()
db = Database(db_path=':memory:')
vs = VectorStore()
orch = Orchestrator(vector_store=vs, embeddings_model=None, memory=None, db=db, settings=settings)

# Add a document chunk
doc = {'id':'d1-1','text':'AI improves diagnosis and enables personalized treatment.','metadata':{'user_id':None,'source':'research.txt'},'embedding':[0.1]*10}
vs.add_documents([doc])

# First question
res1 = orch.handle_query('What does the document say about AI?', top_k=5, use_hybrid=True, user_id=None)
print('First response:', res1.get('answer'))

# Second question (follow-up)
res2 = orch.handle_query('How does AI help with diagnosis?', top_k=5, use_hybrid=True, user_id=None)
print('Second response:', res2.get('answer'))

# Show recent chats stored in DB
recent = db.get_recent_conversation(limit=10)
print('Recent chats:', recent)
