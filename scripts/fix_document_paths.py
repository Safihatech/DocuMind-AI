"""Repair script: locate missing uploaded files and update DB storage_path entries.

Run:
    python scripts/fix_document_paths.py

It will attempt to find files under the workspace `uploads/` directory that match the
`filename` stored in the `documents` table (including UUID-prefixed variants) and
update the `storage_path` field to the resolved absolute path.
"""
from pathlib import Path
from app.core.db import Database

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
UPLOADS_ROOT = WORKSPACE_ROOT / "uploads"
DB_PATH = "app.db"

if __name__ == "__main__":
    db = Database(db_path=DB_PATH)
    docs = db.list_documents()
    updated = 0
    for d in docs:
        doc_id = d.get("id")
        full = db.get_document(doc_id)
        storage_path = full.get("storage_path")
        if storage_path and Path(storage_path).exists():
            print(f"OK: {doc_id} -> {storage_path}")
            continue
        filename = full.get("filename")
        print(f"Searching for missing file for document {doc_id}: {filename}")
        found = None
        for p in UPLOADS_ROOT.rglob("*"):
            try:
                if p.is_file() and p.name.lower().endswith(filename.lower()):
                    found = p.resolve()
                    break
            except Exception:
                continue
        if found:
            cur = db.conn.cursor()
            cur.execute("UPDATE documents SET storage_path = ? WHERE id = ?", (str(found), doc_id))
            db.conn.commit()
            updated += 1
            print(f"Updated document {doc_id} -> {found}")
        else:
            print(f"Not found for document {doc_id}: {filename}")
    print(f"Done. Updated {updated} documents.")
