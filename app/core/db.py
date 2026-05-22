"""SQLite database helper for app users, documents, and chat history."""
from __future__ import annotations
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class Database:
    def __init__(self, db_path: str = "app.db"):
        self.db_path = db_path
        connect_path = self.db_path if self.db_path == ":memory:" else str(Path(self.db_path).resolve())
        self.conn = sqlite3.connect(connect_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_tables()

    def _ensure_tables(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                user_id INTEGER,
                status TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                chunks INTEGER DEFAULT 0
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        def migrate_nullable_user_id(table_name: str, create_sql: str):
            cur.execute(f"PRAGMA table_info({table_name})")
            columns = cur.fetchall()
            column_names = [row[1] for row in columns]
            if 'user_id' not in column_names:
                cur.execute(f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER")
                return

            # If `user_id` exists but is marked NOT NULL, rebuild the table.
            user_id_info = next((row for row in columns if row[1] == 'user_id'), None)
            if user_id_info and user_id_info[3] == 1:
                temp_table = f"{table_name}_temp_migrate"
                cur.execute(create_sql)
                cols = ", ".join(column_names)
                cur.execute(f"INSERT INTO {temp_table} ({cols}) SELECT {cols} FROM {table_name}")
                cur.execute(f"DROP TABLE {table_name}")
                cur.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")

        migrate_nullable_user_id(
            'documents',
            """
            CREATE TABLE IF NOT EXISTS documents_temp_migrate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                user_id INTEGER,
                status TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                chunks INTEGER DEFAULT 0
            )
            """
        )
        migrate_nullable_user_id(
            'chats',
            """
            CREATE TABLE IF NOT EXISTS chats_temp_migrate (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        self.conn.commit()

    def create_user(self, name: str, email: str, password_hash: str) -> int:
        cur = self.conn.cursor()
        created_at = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, created_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        return dict(row) if row else None

    def update_document_status(self, document_id: int, status: str, chunks: Optional[int] = None):
        cur = self.conn.cursor()
        if chunks is not None:
            cur.execute(
                "UPDATE documents SET status = ?, chunks = ? WHERE id = ?",
                (status, chunks, document_id),
            )
        else:
            cur.execute(
                "UPDATE documents SET status = ? WHERE id = ?",
                (status, document_id),
            )
        self.conn.commit()

    def create_document(self, filename: str, storage_path: str, user_id: Optional[int] = None, status: str = "queued") -> int:
        cur = self.conn.cursor()
        uploaded_at = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "INSERT INTO documents (filename, storage_path, user_id, status, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (filename, storage_path, user_id, status, uploaded_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_documents(self, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if user_id is not None:
            cur.execute(
                "SELECT id, filename, status, uploaded_at, chunks FROM documents WHERE user_id = ? ORDER BY id DESC",
                (user_id,),
            )
        else:
            cur.execute(
                "SELECT id, filename, status, uploaded_at, chunks FROM documents ORDER BY id DESC",
            )
        return [dict(row) for row in cur.fetchall()]

    def get_document(self, document_id: int, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        if user_id is not None:
            cur.execute("SELECT * FROM documents WHERE id = ? AND user_id = ?", (document_id, user_id))
        else:
            cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def create_chat(self, question: str, answer: str, user_id: Optional[int] = None) -> int:
        cur = self.conn.cursor()
        created_at = datetime.utcnow().isoformat() + "Z"
        cur.execute(
            "INSERT INTO chats (user_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
            (user_id, question, answer, created_at),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_chats(self, user_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if user_id is not None:
            cur.execute(
                "SELECT id, question, answer, created_at FROM chats WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
        else:
            cur.execute(
                "SELECT id, question, answer, created_at FROM chats ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = [dict(row) for row in cur.fetchall()]
        return list(reversed(rows))

    def get_recent_conversation(self, user_id: Optional[int] = None, limit: int = 5) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        if user_id is not None:
            cur.execute(
                "SELECT question, answer FROM chats WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
        else:
            cur.execute(
                "SELECT question, answer FROM chats ORDER BY id DESC LIMIT ?",
                (limit,),
            )
        rows = [dict(row) for row in cur.fetchall()]
        return list(reversed(rows))

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
