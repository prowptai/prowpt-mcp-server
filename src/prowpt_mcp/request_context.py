"""Per-request context used by the HTTP transport to pass a caller-provided
bearer token (OAuth JWT or API key) through to :mod:`prowpt_mcp.client` without
polluting the tool dispatch signature.

The stdio transport never sets this; it keeps reading ``PROWPT_API_KEY`` from
the environment.
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

_bearer_token: ContextVar[Optional[str]] = ContextVar(
    "prowpt_mcp_bearer_token", default=None,
)


def set_bearer_token(token: Optional[str]) -> object:
    """Set the bearer token for the current context. Returns the token to pass
    back to :func:`reset_bearer_token` so nested contexts restore cleanly."""
    return _bearer_token.set(token)


def reset_bearer_token(token: object) -> None:
    _bearer_token.reset(token)  # type: ignore[arg-type]


def get_bearer_token() -> Optional[str]:
    return _bearer_token.get()
