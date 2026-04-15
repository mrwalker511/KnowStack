"""Sample ORM models for testing extraction."""


class Base:
    pass


class User(Base):
    """A user account."""

    id: int
    email: str
    hashed_password: str

    def __init__(self, email: str, password: str) -> None:
        self.email = email
        self.hashed_password = password

    def verify_password(self, plain: str) -> bool:
        """Check a plain password against the stored hash."""
        return self.hashed_password == plain  # simplified


class Token(Base):
    """Auth token."""

    value: str
    user_id: int
