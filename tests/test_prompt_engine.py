from app.prompt_engine import (
    build_messages,
    extract_new_messages,
    make_rolling_summary,
)


def test_prompt_keeps_summary_and_recent_history():
    result = build_messages(
        incoming=[{"role": "user", "content": "Continue"}],
        history=[{"role": "user", "content": "Earlier"}],
        summary="We were discussing a project.",
        max_messages=10,
    )
    assert result[0]["role"] == "system"
    assert any("project" in str(m["content"]) for m in result)
    assert result[-1]["content"] == "Continue"


def test_summary_is_extractively_built():
    result = make_rolling_summary("", [
        {"role": "user", "content": "Hello there"},
        {"role": "assistant", "content": "Hi"},
    ])
    assert "user: Hello there" in result
    assert "assistant: Hi" in result


def test_full_client_history_only_persists_new_turn():
    stored = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Answer one"},
    ]
    incoming = [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Answer one"},
        {"role": "user", "content": "Second"},
    ]
    assert extract_new_messages(stored, incoming) == [
        {"role": "user", "content": "Second"}
    ]


def test_single_repeated_message_is_a_new_turn():
    repeated = [{"role": "user", "content": "Again"}]
    assert extract_new_messages(repeated, repeated) == repeated
