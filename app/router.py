from __future__ import annotations

import time
from typing import Any

from app.core import SHARED_KEYS, load_models, settings
from app.providers import call_provider, ProviderError
from app.quota import QuotaManager


class ModelRouter:
    def __init__(self):
        self.quota = QuotaManager(settings.database_path)

    def models(self) -> list[dict]:
        return load_models()

    def providers_status(self) -> list[dict]:
        models = self.models()
        providers = sorted({m["provider"] for m in models})
        return [
            {
                "provider": p,
                "shared_key_configured": bool(SHARED_KEYS.get(p)),
                "eligible_models": sum(1 for m in models if m["provider"] == p),
            }
            for p in providers
        ]

    async def complete(
        self,
        requested_model: str,
        messages: list[dict[str, Any]],
        provider_keys: dict[str, str],
        allow_fallback: bool,
        max_tokens: int | None,
        temperature: float,
    ) -> tuple[dict, dict, list[dict[str, str]]]:
        models = self.models()
        if requested_model != "auto":
            selected = [m for m in models if m["id"] == requested_model]
            if not selected:
                raise ValueError("Requested model is not enabled in the free-model catalogue.")
            fallback = [m for m in models if m["id"] != requested_model] if allow_fallback else []
            candidates = selected + sorted(fallback, key=lambda m: m.get("priority", 100))
        else:
            candidates = sorted(models, key=lambda m: m.get("priority", 100))

        failures: list[dict[str, str]] = []
        attempts = 0
        seen_providers: set[str] = set()
        for model in candidates:
            provider = model["provider"]
            if provider in seen_providers:
                continue
            seen_providers.add(provider)
            key = (provider_keys.get(provider) or SHARED_KEYS.get(provider) or "").strip()
            if not key:
                failures.append({"provider": provider, "reason": "No shared or BYOK credential configured."})
                continue

            cooldown = self.quota.remaining(provider, key)
            if cooldown:
                failures.append({"provider": provider, "reason": f"Credential cooling down for {cooldown}s."})
                continue

            attempts += 1
            try:
                result = await call_provider(
                    provider=provider,
                    model=model["provider_model"],
                    messages=messages,
                    api_key=key,
                    timeout=settings.request_timeout,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                self.quota.clear(provider, key)
                return result, model, failures
            except ProviderError as exc:
                reason = f"HTTP {exc.status_code}" if exc.status_code else "Network timeout or connection failure"
                failures.append({"provider": provider, "reason": reason})
                if exc.status_code == 429:
                    self.quota.defer(provider, key, 60, "rate_limit")
                elif exc.status_code in (408, 409, 425, 500, 502, 503, 504) or exc.status_code is None:
                    self.quota.defer(provider, key, 20, "temporary_failure")

            if attempts >= max(1, settings.max_failovers):
                break

        raise RuntimeError("No eligible free provider succeeded. " + "; ".join(
            f'{x["provider"]}: {x["reason"]}' for x in failures
        ))


router = ModelRouter()
