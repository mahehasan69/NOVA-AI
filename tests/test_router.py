import asyncio

from app.providers import ProviderError
from app.router import ModelRouter


def test_explicit_model_is_attempted_before_fallback(monkeypatch):
    catalogue = [
        {"id": "gemini-fast", "provider": "gemini", "provider_model": "gemini-fast", "free": True, "enabled": True, "priority": 10},
        {"id": "groq-fast", "provider": "groq", "provider_model": "groq-fast", "free": True, "enabled": True, "priority": 1},
    ]
    monkeypatch.setattr("app.router.load_models", lambda: catalogue)
    attempts = []

    async def fake_call(provider, **kwargs):
        attempts.append(provider)
        if provider == "gemini":
            raise ProviderError(provider, "rate limited", status_code=429)
        return {"content": "continued", "prompt_tokens": 3, "completion_tokens": 2}

    monkeypatch.setattr("app.router.call_provider", fake_call)
    instance = ModelRouter()
    result, selected, failures = asyncio.run(instance.complete(
        requested_model="gemini-fast",
        messages=[{"role": "user", "content": "hello"}],
        provider_keys={"gemini": "gemini-test-key", "groq": "groq-test-key"},
        allow_fallback=True,
        max_tokens=100,
        temperature=0.2,
    ))

    assert attempts == ["gemini", "groq"]
    assert selected["id"] == "groq-fast"
    assert result["content"] == "continued"
    assert failures[0]["reason"] == "HTTP 429"
