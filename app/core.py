from __future__ import annotations

import json
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    nova_api_key: str = ""
    database_path: str = "./nova.db"
    models_file: str = "./config/models.json"
    request_timeout: float = 35.0
    max_context_messages: int = 24
    max_failovers: int = 3

    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""
    mistral_api_key: str = ""
    cerebras_api_key: str = ""
    cohere_api_key: str = ""
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()


def load_models() -> list[dict]:
    path = Path(settings.models_file)
    if not path.exists():
        raise RuntimeError(f"Model catalogue not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    models = data.get("models", [])
    return [
        item for item in models
        if item.get("enabled") is True and item.get("free") is True
    ]


SHARED_KEYS = {
    "gemini": settings.gemini_api_key,
    "groq": settings.groq_api_key,
    "openrouter": settings.openrouter_api_key,
    "mistral": settings.mistral_api_key,
    "cerebras": settings.cerebras_api_key,
    "cohere": settings.cohere_api_key,
    "cloudflare": settings.cloudflare_api_token,
}
