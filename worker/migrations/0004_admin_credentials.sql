CREATE TABLE IF NOT EXISTS admin_credentials (user_id TEXT PRIMARY KEY,salt TEXT NOT NULL,password_hash TEXT NOT NULL,created_at INTEGER NOT NULL);
