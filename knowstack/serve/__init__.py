"""HTTP server for KnowStack — install with pip install knowstack[serve]."""
from .app import create_app

__all__ = ["create_app"]
