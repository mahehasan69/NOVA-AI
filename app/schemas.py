from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[dict[str, Any]]


class ChatRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage] = Field(min_length=1)
    conversation_id: str | None = None
    provider_keys: dict[str, str] = Field(default_factory=dict, exclude=True)
    allow_fallback: bool = True
    max_tokens: int | None = Field(default=1024, ge=1, le=8192)
    temperature: float = Field(default=0.7, ge=0, le=2)


class ChatChoice(BaseModel):
    index: int = 0
    message: dict[str, Any]
    finish_reason: str = "stop"


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[ChatChoice]
    conversation_id: str
    provider: str
    usage: dict[str, int] = Field(default_factory=dict)
    failovers: list[dict[str, str]] = Field(default_factory=list)
