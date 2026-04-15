"""pytest tests for the auth module — for testing test extraction."""
import pytest
from auth import authenticate, logout


def test_authenticate_returns_token():
    token = authenticate("user@example.com", "hashed")
    assert token.value.startswith("tok_")


def test_authenticate_wrong_password():
    with pytest.raises(ValueError):
        authenticate("user@example.com", "wrong")


@pytest.mark.parametrize("email", ["a@b.com", "x@y.org"])
def test_authenticate_parametrized(email: str):
    token = authenticate(email, "hashed")
    assert token is not None
