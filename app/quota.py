from __future__ import annotations

import hashlib
import sqlite3
import time
from pathlib import Path


class QuotaManager:
    """Persist provider cooldowns without storing API credentials."""

    def __init__(self, database_path: str):
        self.path = database_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS provider_cooldowns (
                    credential_id TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    until_epoch REAL NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def credential_id(provider: str, api_key: str) -> str:
        fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        return hashlib.sha256(f"{provider}:{fingerprint}".encode("utf-8")).hexdigest()

    def remaining(self, provider: str, api_key: str) -> int:
        cid = self.credential_id(provider, api_key)
        with self._connect() as db:
            row = db.execute(
                "SELECT until_epoch FROM provider_cooldowns WHERE credential_id=?",
                (cid,),
            ).fetchone()
        if not row:
            return 0
        seconds = max(0, int(row[0] - time.time()))
        if seconds == 0:
            self.clear(provider, api_key)
        return seconds

    def defer(self, provider: str, api_key: str, seconds: int, reason: str):
        cid = self.credential_id(provider, api_key)
        with self._connect() as db:
            db.execute("""
                INSERT INTO provider_cooldowns(credential_id,provider,reason,until_epoch)
                VALUES(?,?,?,?)
                ON CONFLICT(credential_id) DO UPDATE SET
                    reason=excluded.reason,
                    until_epoch=excluded.until_epoch,
                    updated_at=CURRENT_TIMESTAMP
            """, (cid, provider, reason[:80], time.time() + max(1, seconds)))

    def clear(self, provider: str, api_key: str):
        cid = self.credential_id(provider, api_key)
        with self._connect() as db:
            db.execute("DELETE FROM provider_cooldowns WHERE credential_id=?", (cid,))

    def snapshot(self) -> list[dict]:
        now = time.time()
        with self._connect() as db:
            rows = db.execute("""
                SELECT provider,reason,until_epoch FROM provider_cooldowns
                WHERE until_epoch > ? ORDER BY until_epoch DESC
            """, (now,)).fetchall()
        return [
            {"provider": provider, "reason": reason, "cooldown_seconds": max(0, int(until-now))}
            for provider, reason, until in rows
        ]
