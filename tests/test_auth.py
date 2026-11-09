import pytest

from app.auth import AuthError, AuthStore


def store(tmp_path):
    return AuthStore(str(tmp_path / "auth.db"), "test-secret-that-is-long-enough-for-hmac-signing")


def test_register_login_and_access_token(tmp_path):
    auth = store(tmp_path)
    result = auth.register("Nova@example.com", "a-very-long-password-123")
    assert result["user"]["email"] == "nova@example.com"
    assert auth.verify_access(result["access_token"]) == result["user"]["id"]
    login = auth.login("NOVA@example.com", "a-very-long-password-123")
    assert login["user"]["id"] == result["user"]["id"]


def test_duplicate_email_and_weak_password_rejected(tmp_path):
    auth = store(tmp_path)
    auth.register("a@example.com", "a-very-long-password-123")
    with pytest.raises(AuthError):
        auth.register("A@example.com", "another-long-password")
    with pytest.raises(AuthError):
        auth.register("b@example.com", "short")


def test_refresh_rotates_and_logout_revokes(tmp_path):
    auth = store(tmp_path)
    result = auth.register("a@example.com", "a-very-long-password-123")
    refreshed = auth.refresh(result["refresh_token"])
    assert auth.verify_access(refreshed["access_token"]) == result["user"]["id"]
    with pytest.raises(AuthError):
        auth.refresh(result["refresh_token"])
    auth.logout(refreshed["refresh_token"])
    with pytest.raises(AuthError):
        auth.refresh(refreshed["refresh_token"])


def test_invalid_access_token_rejected(tmp_path):
    auth = store(tmp_path)
    with pytest.raises(AuthError):
        auth.verify_access("not.a.valid-token")
