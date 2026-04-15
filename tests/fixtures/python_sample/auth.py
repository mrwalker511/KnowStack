"""Authentication service for testing."""
from models import Token, User


def authenticate(email: str, password: str) -> Token:
    """Authenticate a user and return a token."""
    user = _find_user(email)
    if not user.verify_password(password):
        raise ValueError("Invalid credentials")
    return _create_token(user)


def _find_user(email: str) -> User:
    """Look up a user by email."""
    return User(email=email, password="hashed")


def _create_token(user: User) -> Token:
    """Create and persist a new auth token."""
    token = Token()
    token.user_id = user.id
    token.value = "tok_" + user.email
    return token


def logout(token_value: str) -> None:
    """Invalidate a token."""
    pass
