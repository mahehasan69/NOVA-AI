from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any


class ConversationStore:
    def __init__(self, database_path: str):
        self.path = database_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    model TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(conversation_id) REFERENCES conversations(id)
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, id)")

    def ensure(self, user_id: str, conversation_id: str | None) -> str:
        cid = conversation_id or str(uuid.uuid4())
        with self._connect() as db:
            row = db.execute(
                "SELECT id FROM conversations WHERE id=? AND user_id=?",
                (cid, user_id),
            ).fetchone()
            if row:
                return cid
            if conversation_id:
                raise PermissionError("Conversation not found for this user.")
            db.execute(
                "INSERT INTO conversations(id,user_id) VALUES(?,?)",
                (cid, user_id),
            )
        return cid

    def history(self, user_id: str, conversation_id: str, limit: int) -> tuple[str, list[dict[str, Any]]]:
        with self._connect() as db:
            row = db.execute(
                "SELECT summary FROM conversations WHERE id=? AND user_id=?",
                (conversation_id, user_id),
            ).fetchone()
            if not row:
                raise PermissionError("Conversation not found for this user.")
            messages = db.execute(
                "SELECT role,content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return row["summary"], [dict(x) for x in reversed(messages)]

    def append(self, user_id: str, conversation_id: str, messages: list[dict], model: str):
        with self._connect() as db:
            owned = db.execute(
                "SELECT id FROM conversations WHERE id=? AND user_id=?",
                (conversation_id, user_id),
            ).fetchone()
            if not owned:
                raise PermissionError("Conversation not found for this user.")
            for msg in messages:
                content = msg.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content, ensure_ascii=False)
                db.execute(
                    "INSERT INTO messages(conversation_id,role,content,model) VALUES(?,?,?,?)",
                    (conversation_id, msg["role"], content, model),
                )
            db.execute(
                "UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (conversation_id,),
            )

    def set_summary(self, user_id: str, conversation_id: str, summary: str):
        with self._connect() as db:
            db.execute(
                "UPDATE conversations SET summary=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?",
                (summary, conversation_id, user_id),
            )

    def get_conversation(self, user_id: str, conversation_id: str):
        summary, messages = self.history(user_id, conversation_id, 200)
        return {"id": conversation_id, "summary": summary, "messages": messages}
