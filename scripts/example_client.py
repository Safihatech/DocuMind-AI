"""Example client: upload a file and run a QA query against the local server.

Usage:
  python scripts/example_client.py --server http://127.0.0.1:8001 --file test_upload4.txt

The script uploads the file to `/documents/upload` and then sends a simple QA query
to `/qa/query` asking for a summary. Adjust `--server` if your backend runs on
another host/port.
"""
import argparse
import time
import requests
import sys


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--server", default="http://127.0.0.1:8001", help="Backend base URL")
    p.add_argument("--file", default="test_upload4.txt", help="Path to file to upload (relative to repo root or absolute)")
    p.add_argument("--wait", type=float, default=2.0, help="Seconds to wait after upload before QA query")
    args = p.parse_args()

    upload_url = args.server.rstrip("/") + "/documents/upload"
    qa_url = args.server.rstrip("/") + "/qa/query"

    print(f"Uploading {args.file} to {upload_url}")
    try:
        with open(args.file, "rb") as fh:
            files = {"file": (args.file, fh)}
            resp = requests.post(upload_url, files=files, timeout=60)
    except FileNotFoundError:
        print("File not found:", args.file)
        sys.exit(2)
    except Exception as e:
        print("Upload failed:", e)
        sys.exit(1)

    print("Upload response status:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text[:1000])

    print(f"Waiting {args.wait} seconds for server to process...")
    time.sleep(args.wait)

    query = {
        "query": "Please provide a concise summary of the uploaded document."
    }
    print(f"Querying QA endpoint {qa_url} with query: {query['query']!r}")
    try:
        r = requests.post(qa_url, json=query, timeout=60)
        print("QA response status:", r.status_code)
        try:
            print(r.json())
        except Exception:
            print(r.text[:2000])
    except Exception as e:
        print("QA request failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
