Quick Start Examples

Prerequisites
- Python 3.10+ and a virtual environment
- Tesseract OCR installed and on PATH for PDF image OCR
- Valid API keys for LLMs/embeddings set as environment variables (see below)

Environment variables
- GROQ_API_KEY: your Groq API key
- GROQ_MODEL: meta-llama-8b (or another model you have access to)
- GEMINI_API_KEY: your Google Gemini embedding key (optional; fallback exists)

Start MCP servers (optional)
- Run local MCP wrappers (if using them):

```powershell
python scripts/run_mcp_servers.py
# or
docker-compose up
```

Start backend

```powershell
# from repository root
uvicorn app.main:app --reload --port 8001
```

Upload example

```bash
curl -v -F "file=@test_upload.txt" http://127.0.0.1:8001/documents/upload
```

QA query example

```bash
curl -X POST http://127.0.0.1:8001/qa/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What is this document about?","model":"meta-llama-8b"}'
```

Notes
- If your Groq or Gemini keys lack access, the app falls back to deterministic or context-only behavior; update keys to enable full LLM/embed functionality.
- If OCR is required, install Tesseract (https://github.com/tesseract-ocr/tesseract) and ensure `tesseract` is on your PATH.
