from __future__ import annotations

import httpx


OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


async def discover_openrouter_free_models(timeout: float = 20.0) -> list[dict]:
    """Discover candidates with zero listed prompt and completion price.

    Discovery is advisory only: returned candidates are never automatically
    enabled. Availability, free quotas, terms and model quality must be reviewed.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(OPENROUTER_MODELS_URL)
        response.raise_for_status()
        payload = response.json()

    candidates = []
    for item in payload.get("data", []):
        pricing = item.get("pricing") or {}
        try:
            prompt_price = float(pricing.get("prompt", "nan"))
            completion_price = float(pricing.get("completion", "nan"))
        except (TypeError, ValueError):
            continue
        if prompt_price != 0 or completion_price != 0:
            continue
        candidates.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "provider": "openrouter",
            "free_price_candidate": True,
            "context_length": item.get("context_length"),
            "architecture": item.get("architecture", {}),
            "supported_parameters": item.get("supported_parameters", []),
            "pricing": {"prompt": pricing.get("prompt"), "completion": pricing.get("completion")},
            "requires_manual_review": True,
        })
    return candidates
