"""Helper to run MCP wrapper servers locally during development."""
import subprocess
import sys


if __name__ == "__main__":
    print("Starting MCP wrapper servers...")
    subprocess.run([sys.executable, "-m", "uvicorn", "app.mcp_servers.web_search_tavily.server:app", "--port", "8001", "--reload"], check=False)
    subprocess.run([sys.executable, "-m", "uvicorn", "app.mcp_servers.chroma_wrapper.server:app", "--port", "8002", "--reload"], check=False)
    subprocess.run([sys.executable, "-m", "uvicorn", "app.mcp_servers.document_processing.server:app", "--port", "8003", "--reload"], check=False)
