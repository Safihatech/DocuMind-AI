"""SQLite-backed conversation memory for simple persistence.

Implements a small table to store conversation turns with timestamps and
provides the same `add(user, bot)` and `get()` interface as the in-memory
`ConversationMemory` so it can be swapped in transparently.
"""
from __future__ import annotations
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional


class SQLiteConversationMemory:
    def __init__(self, db_path: str = "memory.db", max_len: int = 1000):
        self.db_path = db_path
        self.max_len = max_len
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._ensure_table()

    def _ensure_table(self):
        cur = self.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user TEXT NOT NULL,
                bot TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def add(self, user: str, bot: str):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO conversations (timestamp, user, bot) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat() + "Z", user, bot),
        )
        self.conn.commit()
        # Optionally trim old rows to cap size
        cur.execute("SELECT COUNT(1) FROM conversations")
        count = cur.fetchone()[0]
        if count > self.max_len:
            # delete oldest rows beyond max_len
            to_delete = count - self.max_len
            cur.execute(
                "DELETE FROM conversations WHERE id IN (SELECT id FROM conversations ORDER BY id ASC LIMIT ?)",
                (to_delete,),
            )
            self.conn.commit()

    def get(self, limit: Optional[int] = None) -> List[Dict]:
        cur = self.conn.cursor()
        sql = "SELECT id, timestamp, user, bot FROM conversations ORDER BY id DESC"
        params: tuple = ()
        if limit is not None:
            sql = sql + " LIMIT ?"
            params = (limit,)

        cur.execute(sql, params)
        rows = cur.fetchall()
        # Return in chronological order (oldest first)
        rows = list(reversed(rows))
        return [
            {"id": r[0], "timestamp": r[1], "user": r[2], "bot": r[3]}
            for r in rows
        ]

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
