from __future__ import annotations

import asyncio
import httpx
from typing import Any


OPENAI_COMPATIBLE = {
    "groq": "https://api.groq.com/openai/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "mistral": "https://api.mistral.ai/v1/chat/completions",
    "cerebras": "https://api.cerebras.ai/v1/chat/completions",
    "cohere": "https://api.cohere.com/compatibility/v1/chat/completions",
}


class ProviderError(Exception):
    def __init__(self, provider: str, message: str, status_code: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.retryable = retryable


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Preserve text parts; provider-specific multimodal adaptation is future work.
        return "\n".join(str(x.get("text", "")) for x in content if isinstance(x, dict))
    return str(content)


async def call_provider(
    provider: str,
    model: str,
    messages: list[dict[str, Any]],
    api_key: str,
    timeout: float,
    max_tokens: int | None,
    temperature: float,
) -> dict[str, Any]:
    if provider == "gemini":
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        system = "\n".join(
            m["content"] for m in messages if m["role"] == "system" and isinstance(m["content"], str)
        )
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": _extract_text(msg["content"])}]})
        payload: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        if max_tokens:
            payload["generationConfig"]["maxOutputTokens"] = max_tokens
        headers = {"x-goog-api-key": api_key}
    else:
        url = OPENAI_COMPATIBLE.get(provider)
        if not url:
            raise ProviderError(provider, "Provider adapter is not implemented.", retryable=False)
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise ProviderError(provider, f"Provider connection failed: {type(exc).__name__}") from exc

    if response.status_code >= 400:
        detail = "Provider request failed"
        try:
            body = response.json()
            detail = str(body.get("error", body.get("message", detail)))
        except ValueError:
            pass
        # Do not return provider response bodies that might contain sensitive data.
        retryable = response.status_code in (408, 409, 425, 429, 500, 502, 503, 504)
        raise ProviderError(provider, detail[:300], response.status_code, retryable)

    data = response.json()
    if provider == "gemini":
        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderError(provider, "Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        usage = data.get("usageMetadata", {})
        return {
            "content": text,
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
        }

    choices = data.get("choices", [])
    if not choices:
        raise ProviderError(provider, "Provider returned no choices.")
    message = choices[0].get("message", {})
    usage = data.get("usage", {})
    return {
        "content": message.get("content", ""),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }
