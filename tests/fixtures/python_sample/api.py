"""FastAPI-style endpoint stubs for testing endpoint extraction."""
from auth import authenticate, logout


class app:
    @staticmethod
    def get(path: str):
        def decorator(fn):
            return fn
        return decorator

    @staticmethod
    def post(path: str):
        def decorator(fn):
            return fn
        return decorator


@app.post("/auth/login")
def login(email: str, password: str):
    """Log in and return a token."""
    return authenticate(email, password)


@app.post("/auth/logout")
def do_logout(token: str):
    """Invalidate an auth token."""
    logout(token)
    return {"status": "ok"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
