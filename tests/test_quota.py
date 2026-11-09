from app.quota import QuotaManager


def test_quota_cooldown_is_persisted_and_key_is_not_exposed(tmp_path):
    db = str(tmp_path / "quota.db")
    manager = QuotaManager(db)
    key = "test-secret-provider-key"

    assert manager.remaining("groq", key) == 0
    manager.defer("groq", key, 120, "rate_limit")

    # A new manager instance reads the same persisted cooldown.
    restarted = QuotaManager(db)
    assert restarted.remaining("groq", key) > 0
    snapshot = restarted.snapshot()
    assert snapshot[0]["provider"] == "groq"
    assert "credential_id" not in snapshot[0]
    assert key not in str(snapshot)


def test_quota_cooldowns_are_isolated_by_credential(tmp_path):
    manager = QuotaManager(str(tmp_path / "quota.db"))
    manager.defer("groq", "user-one-key", 120, "rate_limit")

    assert manager.remaining("groq", "user-one-key") > 0
    assert manager.remaining("groq", "user-two-key") == 0


def test_quota_clear_removes_cooldown(tmp_path):
    manager = QuotaManager(str(tmp_path / "quota.db"))
    manager.defer("gemini", "my-key", 120, "temporary_failure")
    manager.clear("gemini", "my-key")

    assert manager.remaining("gemini", "my-key") == 0
