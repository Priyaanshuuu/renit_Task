"""Vercel's repository-root ASGI entrypoint."""

from backend.app.main import app

__all__ = ["app"]
