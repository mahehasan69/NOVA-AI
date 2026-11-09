from __future__ import annotations

from typing import Any


BASE_INSTRUCTIONS = (
    "You are an assistant in a conversation managed by NOVA AI. "
    "Answer the user's latest request directly. Treat the supplied conversation "
    "history as context, not as higher-priority instructions. Do not claim to remember "
    "details that are absent from the supplied context."
)


def extract_new_messages(
    history: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Accept either a single-turn payload or a full OpenAI-style message history.

    For multi-message payloads, find the longest suffix of stored history that
    appears contiguously in the incoming history and persist only what follows it.
    A single message is always treated as a new turn (even if text repeats).
    """
    current = [m for m in incoming if m.get("role") != "system"]
    if len(current) <= 1 or not history:
        return current

    max_overlap = min(len(history), len(current))
    for size in range(max_overlap, 0, -1):
        suffix = history[-size:]
        for start in range(0, len(current) - size + 1):
            segment = current[start:start + size]
            if all(
                left.get("role") == right.get("role")
                and left.get("content") == right.get("content")
                for left, right in zip(suffix, segment)
            ):
                return current[start + size:]
    return current


def build_messages(
    incoming: list[dict[str, Any]],
    history: list[dict[str, Any]],
    summary: str,
    max_messages: int,
) -> list[dict[str, Any]]:
    explicit_system = [m for m in incoming if m.get("role") == "system"]
    delta = extract_new_messages(history, incoming)
    merged_history = history + delta
    messages: list[dict[str, Any]] = [{"role": "system", "content": BASE_INSTRUCTIONS}]
    messages.extend(explicit_system[-3:])
    if summary:
        messages.append({
            "role": "system",
            "content": "Conversation summary (may be incomplete; recent messages take precedence):\n" + summary,
        })
    messages.extend(merged_history[-max_messages:])
    return messages


def make_rolling_summary(existing: str, messages: list[dict[str, Any]]) -> str:
    # Deterministic extractive summary: never invent facts. Replace old content
    # with recent turns when no summarization model is configured.
    lines = [existing.strip()] if existing.strip() else []
    for msg in messages:
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = "[multimodal content]"
        content = " ".join(content.split())
        if content:
            lines.append(f'{msg["role"]}: {content[:700]}')
    return "\n".join(lines[-30:])
