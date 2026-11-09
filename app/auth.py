from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class AuthError(ValueError):
    pass


class AuthStore:
    """Small SQLite account store with scrypt password hashes and rotating refresh tokens."""

    def __init__(self, database_path: str, secret: str, access_ttl: int = 900, refresh_ttl: int = 2592000):
        if len(secret) < 32:
            raise ValueError("NOVA_AUTH_SECRET must contain at least 32 characters.")
        self.path = database_path
        self.secret = secret.encode()
        self.access_ttl = access_ttl
        self.refresh_ttl = refresh_ttl
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL, created_at INTEGER NOT NULL
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS refresh_sessions (
                token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_sessions(user_id)")

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _password_hash(password: str) -> str:
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
        return "scrypt$" + _b64(salt) + "$" + _b64(digest)

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            algorithm, salt_text, digest_text = encoded.split("$", 2)
            if algorithm != "scrypt":
                return False
            expected = _unb64(digest_text)
            actual = hashlib.scrypt(password.encode(), salt=_unb64(salt_text), n=2**14, r=8, p=1, dklen=len(expected))
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError):
            return False

    def _access_token(self, user_id: str) -> str:
        now = int(time.time())
        header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = _b64(json.dumps({"sub": user_id, "iat": now, "exp": now + self.access_ttl}, separators=(",", ":")).encode())
        body = header + "." + payload
        signature = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
        return body + "." + signature

    def verify_access(self, token: str) -> str:
        try:
            header, payload, signature = token.split(".")
            body = header + "." + payload
            expected = _b64(hmac.new(self.secret, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise AuthError("Invalid access token.")
            claims = json.loads(_unb64(payload))
            if claims.get("exp", 0) <= int(time.time()) or not isinstance(claims.get("sub"), str):
                raise AuthError("Access token expired or invalid.")
            return claims["sub"]
        except AuthError:
            raise
        except Exception as exc:
            raise AuthError("Invalid access token.") from exc

    def _issue(self, user_id: str) -> dict[str, Any]:
        refresh = secrets.token_urlsafe(48)
        now = int(time.time())
        with self._connect() as db:
            db.execute("INSERT INTO refresh_sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                       (hashlib.sha256(refresh.encode()).hexdigest(), user_id, now + self.refresh_ttl, now))
        return {"access_token": self._access_token(user_id), "refresh_token": refresh,
                "token_type": "bearer", "expires_in": self.access_ttl}

    def register(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
            raise AuthError("Enter a valid email address.")
        if len(password) < 12 or len(password) > 256:
            raise AuthError("Password must be between 12 and 256 characters.")
        user_id = secrets.token_urlsafe(18)
        try:
            with self._connect() as db:
                db.execute("INSERT INTO users(id,email,password_hash,created_at) VALUES(?,?,?,?)",
                           (user_id, email, self._password_hash(password), int(time.time())))
        except sqlite3.IntegrityError as exc:
            raise AuthError("An account with this email already exists.") from exc
        return {"user": {"id": user_id, "email": email}, **self._issue(user_id)}

    def login(self, email: str, password: str) -> dict[str, Any]:
        with self._connect() as db:
            user = db.execute("SELECT id,email,password_hash FROM users WHERE email=? COLLATE NOCASE",
                              (email.strip(),)).fetchone()
        if not user or not self._verify_password(password, user["password_hash"]):
            raise AuthError("Incorrect email or password.")
        return {"user": {"id": user["id"], "email": user["email"]}, **self._issue(user["id"])}

    def refresh(self, token: str) -> dict[str, Any]:
        digest = hashlib.sha256(token.encode()).hexdigest()
        now = int(time.time())
        with self._connect() as db:
            row = db.execute("SELECT user_id,expires_at FROM refresh_sessions WHERE token_hash=?", (digest,)).fetchone()
            if not row or row["expires_at"] <= now:
                db.execute("DELETE FROM refresh_sessions WHERE token_hash=?", (digest,))
                raise AuthError("Refresh token is invalid or expired.")
            # Rotate: the old token is invalidated before a new one is issued.
            db.execute("DELETE FROM refresh_sessions WHERE token_hash=?", (digest,))
            user_id = row["user_id"]
        return self._issue(user_id)

    def logout(self, token: str) -> None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._connect() as db:
            db.execute("DELETE FROM refresh_sessions WHERE token_hash=?", (digest,))

    def get_user(self, user_id: str) -> dict[str, str] | None:
        with self._connect() as db:
            row = db.execute("SELECT id,email FROM users WHERE id=?", (user_id,)).fetchone()
        return {"id": row["id"], "email": row["email"]} if row else None
