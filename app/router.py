from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import Any

from app.core import SHARED_KEYS, load_models, settings
from app.providers import call_provider, ProviderError


class ModelRouter:
    def __init__(self):
        # Cooldowns are scoped to a credential fingerprint so one BYOK user's
        # exhausted quota does not block every other user's key for that provider.
        self.cooldowns: dict[str, float] = defaultdict(float)

    @staticmethod
    def _cooldown_id(provider: str, key: str) -> str:
        fingerprint = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        return f"{provider}:{fingerprint}"

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
            # A manually selected model is always attempted first.
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

            cooldown_id = self._cooldown_id(provider, key)
            if self.cooldowns[cooldown_id] > time.time():
                failures.append({"provider": provider, "reason": "Credential is temporarily cooling down after a provider limit or outage."})
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
                self.cooldowns[cooldown_id] = 0
                return result, model, failures
            except ProviderError as exc:
                # Do not echo arbitrary provider response bodies to the client.
                reason = f"HTTP {exc.status_code}" if exc.status_code else "Network timeout or connection failure"
                failures.append({"provider": provider, "reason": reason})
                if exc.status_code == 429:
                    self.cooldowns[cooldown_id] = time.time() + 60
                elif exc.status_code in (408, 409, 425, 500, 502, 503, 504) or exc.status_code is None:
                    self.cooldowns[cooldown_id] = time.time() + 20

            if attempts >= max(1, settings.max_failovers):
                break

        raise RuntimeError("No eligible free provider succeeded. " + "; ".join(
            f'{x["provider"]}: {x["reason"]}' for x in failures
        ))


router = ModelRouter()
