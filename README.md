# Advanced Multi-Agent RAG System

A FastAPI-based Retrieval-Augmented Generation (RAG) system with a multi-agent architecture for intelligent document Q&A. Features include hybrid search (vector + keyword), conversation memory, web search integration, PDF OCR support, and semantic chunking.

## Features

- **Multi-Agent Architecture**: Orchestrator coordinates Query Analyzer, Retrieval, Reranker, Generator, and Citation agents using `LangGraph`
- **Hybrid Search**: Combines vector embeddings and keyword-based search for better retrieval
- **Document Processing**: Supports PDF, TXT, MD, images (PNG, JPG, BMP, TIFF) with OCR for embedded images
- **Semantic Chunking**: Intelligent text splitting that preserves paragraph and sentence boundaries
- **Conversation Memory**: Tracks conversation history for follow-up questions with context
- **Web Search Integration**: Optional MCP-based web search augmentation
- **MCP Server Support**: Extensible Model Context Protocol (MCP) servers for vector DB, document processing, and web search
- **Vanilla JS Frontend**: Clean, responsive UI with no framework dependencies
- **Hypercorn Server**: High-performance ASGI server without reload issues on Windows

## Quick Start

### 1. Setup (Windows PowerShell)

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2. Install Tesseract OCR (Required for Image Extraction)

**Windows**:
```powershell
choco install tesseract
# Or download from: https://github.com/tesseract-ocr/tesseract/releases
```

**macOS**:
```bash
brew install tesseract
```

### 3. Run the Server

Using the provided PowerShell script (recommended):
```powershell
.\scripts\start_server.ps1 -Open
```

Or manually with Hypercorn:
```powershell
& ".\.venv\Scripts\python.exe" -m hypercorn app.main:app --bind 127.0.0.1:8000 --workers 1 --log-level info
```

The app will be available at: `http://127.0.0.1:8000`

### Alternative: Run with PowerShell + Uvicorn

If you prefer to run the app manually in PowerShell using `uvicorn`, run these commands from your project folder:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& .venv\Scripts\Activate.ps1
cd <your-project-directory>
uvicorn app.main:app --reload
```

Replace `<your-project-directory>` with your project folder if not already there.

### Run with Docker (recommended for reproducible local setup)

Build and start the API, MCP wrappers, Redis, and Celery worker using Docker Compose:

```bash
# build images (only required once or after dependency changes)
docker compose build
# start API, MCP services, Redis and Celery worker in the background
docker compose up -d
# (optional) start/scale only the celery worker if you modified configuration
docker compose up -d celery_worker
# View API logs
docker compose logs -f api
```

For Windows users, run the helper script to start Docker and print a clickable link:

```powershell
.\scripts\start_docker.ps1
```

Or to build before starting:

```powershell
.\scripts\start_docker.ps1 -Build
```

Or to build, start, and open the browser immediately:

```powershell
.\scripts\start_docker.ps1 -Build -Open
```

The compose config includes a Redis instance used as the Celery broker and status store. By default `REDIS_URL` is set to `redis://redis:6379/0`. See `.env.example` for configurable environment variables.

## API Endpoints

### Document Management
- **POST `/documents/upload`** - Upload and process a document
  - Accepts: PDF, TXT, MD, PNG, JPG, JPEG, BMP, TIFF
  - Returns: document chunks count and storage path

### Question Answering
- **POST `/qa/query`** - Ask a question against uploaded documents
  - Request: `{"query": "...", "top_k": 5, "use_hybrid": true}`
  - Response: `{"answer": "...", "citations": [...], "follow_up": "...", "web_search": [...]}`

### Hybrid Search
- **POST `/search/hybrid`** - Execute hybrid search
  - Request: `{"query": "...", "top_k": 5}`
  - Response: `{"query": "...", "vector": [...], "keyword": [...]}`

### Agent Status
- **GET `/agents/status`** - Check agent system health and diagnostics
  - Returns memory count, indexed document count, Groq and web search configuration state
- **GET `/agents/memory`** - Retrieve conversation history

### Health
- **GET `/health`** - Health check endpoint

## Multi-Agent Pipeline

The system processes queries through a coordinated `LangGraph` pipeline:

1. **Query Analyzer** - Detects intent, decides retrieval strategy, determines if web search is needed
2. **Retrieval Agent** - Performs hybrid search (vector + keyword) and optional web search
3. **Reranker Agent** - Re-ranks candidates using relevance scoring
4. **Generator Agent** - Generates answer using context, web results, and conversation memory
5. **Citation Agent** - Formats sources with metadata (page numbers, upload time, etc.)
6. **Memory Agent** - Stores conversation turns to support follow-up questions

## Configuration

Set environment variables in `.env`:

```env
GROQ_API_KEY=<optional-groq-key-for-production-generation>
CHROMA_API_URL=http://localhost:8001
WEB_SEARCH_API_URL=http://localhost:8002/search
DOCUMENT_PROCESSING_API_URL=http://localhost:8003/process
```

## MCP Servers (Optional)

Run optional MCP servers for scalable processing:

```powershell
python .\scripts\run_mcp_servers.py
```

This starts:
- **Chroma Wrapper** (port 8001) - Vector database MCP
- **Web Search** (port 8002) - Web search MCP
- **Document Processing** (port 8003) - Document ingestion MCP

## Document Support

| Format | Support | Notes |
|--------|---------|-------|
| PDF    | ✅      | Text extraction + OCR for embedded images |
| TXT    | ✅      | Plain text files |
| MD     | ✅      | Markdown files (treated as plain text) |
| PNG    | ✅      | OCR extraction |
| JPG    | ✅      | OCR extraction |
| TIFF   | ✅      | OCR extraction |
| BMP    | ✅      | OCR extraction |

## Project Structure

```
app/
├── agents/              # Multi-agent components
│   ├── orchestrator.py  # Main pipeline coordinator
│   ├── query_analyzer.py
│   ├── retrieval.py
│   ├── reranker.py
│   ├── generator.py
│   ├── citation.py
│   └── document_processor.py
├── api/routes/          # REST endpoints
│   ├── qa.py
│   ├── documents.py
│   ├── search.py
│   └── agents.py
├── core/                # Core utilities
│   ├── embeddings.py    # Embedding generation with fallback
│   ├── vector_store.py  # ChromaDB wrapper
│   ├── memory.py        # Conversation memory
│   ├── pdf_processing.py
│   ├── ocr.py
│   └── utils.py
├── mcp_servers/         # MCP implementations
│   ├── chroma_wrapper/
│   ├── web_search_tavily/
│   └── document_processing/
├── main.py              # FastAPI app
└── config.py            # Settings

frontend/
├── index.html           # Main UI
├── app.js              # Client-side app logic
└── styles.css          # Styling

scripts/
├── start_server.ps1    # PowerShell startup script
└── run_mcp_servers.py  # MCP server launcher

tests/                  # Unit tests
```

## Testing

Run tests:
```powershell
pytest -q
```

Run specific test:
```powershell
pytest tests/test_processing.py -v
```

## Development

### Embedding Model
The system uses `sentence-transformers` (all-MiniLM-L6-v2) by default. If unavailable, it falls back to a deterministic hash-based encoder for development.

### Web Search
Web search integration is optional and requires setting `WEB_SEARCH_API_URL`. Without it, the system operates in document-only mode.

### LLM Generation
Answer generation uses Groq API if `GROQ_API_KEY` is set. Otherwise, it returns a fallback response based on retrieved documents.

## Performance Notes

- **Single Worker**: Configured for Windows compatibility (multiprocess/reload can cause socket issues on Windows)
- **Lazy Loading**: Heavy models (embeddings) load on first use to speed up startup
- **Chunking**: Documents are chunked with overlap (900 char chunks, 200 char overlap)
- **Local Index**: Hybrid search maintains an in-memory local index for keyword search

## Troubleshooting

### Tesseract Not Found
Ensure Tesseract is installed and in system PATH. On Windows, you may need to add the installation directory to PATH manually.

### Upload Fails with "Upload failed"
Check `logs/error.log` for detailed error messages. Common issues:
- Unsupported file type
- File too large
- OCR service not available

### Web Search Returns Empty
Ensure `WEB_SEARCH_API_URL` is set and the MCP server is running.

### Slow First Query
The embeddings model loads on first use. Subsequent queries will be faster.

## License

This project is provided as-is for educational and development purposes.

## Architecture Diagram

```
User Query
    ↓
Query Analyzer (intent detection)
    ↓
Retrieval Agent (hybrid search + web search)
    ↓
Reranker (relevance scoring)
    ↓
Generator (answer generation with memory context)
    ↓
Citation Agent (format sources)
    ↓
Response (answer + citations + web results)
```
