from __future__ import annotations

import secrets
import uuid

from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.core import settings
from app.memory import ConversationStore
from app.prompt_engine import build_messages, extract_new_messages, make_rolling_summary
from app.router import router
from app.radar import discover_openrouter_free_models
from app.schemas import ChatRequest, ChatResponse, ChatChoice


app = FastAPI(
    title="NOVA AI Gateway",
    version="0.1.0",
    description="Free-first multi-provider AI gateway with conversation continuity and automatic failover.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-NOVA-User"],
)

store = ConversationStore(settings.database_path)


def authenticate(
    x_api_key: str | None = Header(default=None),
    x_nova_user: str | None = Header(default=None),
) -> str:
    if settings.nova_api_key:
        if not x_api_key or not secrets.compare_digest(x_api_key, settings.nova_api_key):
            raise HTTPException(status_code=401, detail="Invalid NOVA API key.")
    elif x_nova_user is None:
        # Local development only. Set NOVA_API_KEY and replace this identity
        # scheme with real account authentication before public deployment.
        x_nova_user = "local-developer"
    user_id = (x_nova_user or "local-developer").strip()
    if not user_id or len(user_id) > 128:
        raise HTTPException(status_code=400, detail="Invalid user identity.")
    return user_id


@app.get("/")
def root():
    return {"name": "NOVA AI Gateway", "version": app.version, "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "ok", "service": "nova-ai-gateway"}


@app.get("/v1/models")
def list_models(_: str = Depends(authenticate)):
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "owned_by": m["provider"],
                "free": True,
                "capabilities": m.get("capabilities", []),
                "context_window": m.get("context_window"),
            }
            for m in router.models()
        ],
    }


@app.get("/v1/providers")
def list_providers(_: str = Depends(authenticate)):
    return {"providers": router.providers_status()}


@app.get("/v1/quota/status")
def quota_status(_: str = Depends(authenticate)):
    # Exposes provider names and cooldowns only; never credential fingerprints or keys.
    return {"cooldowns": router.quota.snapshot()}


@app.get("/v1/radar/openrouter/free")
async def openrouter_free_radar(_: str = Depends(authenticate)):
    try:
        candidates = await discover_openrouter_free_models(settings.request_timeout)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Model discovery is temporarily unavailable.") from exc
    return {
        "source": "OpenRouter public model catalogue",
        "count": len(candidates),
        "automatic_enable": False,
        "candidates": candidates,
    }


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat(body: ChatRequest, user_id: str = Depends(authenticate)):
    if not body.messages:
        raise HTTPException(status_code=400, detail="At least one message is required.")
    if len(body.provider_keys) > 12:
        raise HTTPException(status_code=400, detail="Too many provider keys supplied.")
    for provider, key in body.provider_keys.items():
        if not provider.isidentifier() or not isinstance(key, str) or len(key) > 512:
            raise HTTPException(status_code=400, detail="Invalid provider key entry.")

    incoming = [m.model_dump() for m in body.messages]
    try:
        conversation_id = store.ensure(user_id, body.conversation_id)
        summary, history = store.history(user_id, conversation_id, settings.max_context_messages)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    prompt = build_messages(
        incoming=incoming,
        history=history,
        summary=summary,
        max_messages=settings.max_context_messages,
    )

    try:
        result, selected_model, failures = await router.complete(
            requested_model=body.model,
            messages=prompt,
            provider_keys=body.provider_keys,
            allow_fallback=body.allow_fallback,
            max_tokens=body.max_tokens,
            temperature=body.temperature,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    assistant_message = {"role": "assistant", "content": result["content"]}
    new_user_messages = extract_new_messages(history, incoming)
    persisted = new_user_messages + [assistant_message]
    try:
        store.append(user_id, conversation_id, persisted, selected_model["id"])
        updated_summary = make_rolling_summary(summary, persisted)
        store.set_summary(user_id, conversation_id, updated_summary)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return ChatResponse(
        id="nova-" + uuid.uuid4().hex,
        model=selected_model["id"],
        conversation_id=conversation_id,
        provider=selected_model["provider"],
        choices=[ChatChoice(message=assistant_message)],
        usage={
            "prompt_tokens": int(result.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(result.get("completion_tokens", 0) or 0),
            "total_tokens": int(result.get("prompt_tokens", 0) or 0) + int(result.get("completion_tokens", 0) or 0),
        },
        failovers=failures,
    )


@app.get("/v1/conversations/{conversation_id}")
def get_conversation(conversation_id: str, user_id: str = Depends(authenticate)):
    try:
        return store.get_conversation(user_id, conversation_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
