"""Streamable HTTP transport for the Prowpt MCP server.

Exposes the same tools that the stdio transport serves, but over HTTP using
the MCP "Streamable HTTP" transport (single ``POST``/``GET`` endpoint that
multiplexes JSON-RPC requests and, optionally, SSE streams for server→client
messages).

Every request must carry an ``Authorization: Bearer <token>`` header. The
token is forwarded verbatim to the Prowpt REST API, so both existing API
keys (``pk_live_...``) and — once the OAuth AS is live — OAuth-issued JWTs
work without further changes here.

Run with::

    prowpt-mcp --transport http --bind 0.0.0.0:8001

The ``/mcp`` endpoint speaks MCP; ``/healthz`` is a tiny liveness probe.
"""
from __future__ import annotations

import contextlib
import logging
from typing import AsyncIterator

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.types import ASGIApp, Receive, Scope, Send

from prowpt_mcp.request_context import reset_bearer_token, set_bearer_token

logger = logging.getLogger("prowpt_mcp.http")


class _McpPathNormaliser:
    """Rewrites a bare ``/mcp`` path to ``/mcp/`` so both forms route to the
    single Streamable HTTP mount without Starlette issuing a 307 redirect
    (some MCP clients, notably in-browser connectors, don't follow them).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
            scope["raw_path"] = b"/mcp/"
        await self.app(scope, receive, send)


class _BearerAuthMiddleware:
    """ASGI middleware that extracts ``Authorization: Bearer <token>`` and
    stores it in a contextvar that MCP tool handlers read via
    :mod:`prowpt_mcp.request_context`.

    The token is NOT validated here; validation happens at the Prowpt REST API
    when the tool call is executed. Missing credentials return ``401`` with
    a ``WWW-Authenticate`` challenge that points to the OAuth discovery
    document (per RFC 9728 / MCP auth spec), so clients can perform Dynamic
    Client Registration automatically.
    """

    def __init__(self, app: ASGIApp, *, resource_metadata_url: str,
                 require_auth: bool) -> None:
        self.app = app
        self.resource_metadata_url = resource_metadata_url
        self.require_auth = require_auth

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path == "/healthz" or path.startswith("/.well-known/"):
            await self.app(scope, receive, send)
            return

        token = _extract_bearer(scope)
        if not token and self.require_auth:
            await _send_401(send, self.resource_metadata_url)
            return

        reset = set_bearer_token(token)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_bearer_token(reset)


def _extract_bearer(scope: Scope) -> str | None:
    for name, value in scope.get("headers") or []:
        if name == b"authorization":
            decoded = value.decode("latin-1", errors="ignore").strip()
            if decoded.lower().startswith("bearer "):
                return decoded[7:].strip() or None
    return None


async def _send_401(send: Send, resource_metadata_url: str) -> None:
    challenge = (
        f'Bearer realm="prowpt", '
        f'resource_metadata="{resource_metadata_url}"'
    )
    body = b'{"error":"unauthorized","error_description":"Missing or invalid bearer token"}'
    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", b"application/json"),
            (b"www-authenticate", challenge.encode("latin-1")),
            (b"content-length", str(len(body)).encode("latin-1")),
        ],
    })
    await send({"type": "http.response.body", "body": body})


async def _healthz(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "prowpt-mcp"})


def build_asgi_app(mcp_server, *,
                   api_url: str,
                   require_auth: bool = True,
                   stateless: bool = True,
                   json_response: bool = False) -> Starlette:
    """Build the Starlette ASGI app that hosts the MCP server over HTTP.

    Parameters
    ----------
    mcp_server:
        The low-level :class:`mcp.server.Server` instance (already populated
        with tools/resources).
    api_url:
        Public URL of the Prowpt backend; used to advertise the OAuth
        protected-resource metadata URL in ``WWW-Authenticate`` challenges.
    require_auth:
        When ``True`` (default), unauthenticated requests get ``401``. Set to
        ``False`` only for local debugging.
    stateless:
        Use the stateless Streamable HTTP mode — each request is handled
        independently, matching how public connectors (Claude.ai, ChatGPT)
        typically speak to remote MCP servers.
    json_response:
        When ``True``, force JSON responses instead of SSE. Useful for
        clients that don't stream.
    """
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,
        json_response=json_response,
        stateless=stateless,
    )

    async def handle_streamable_http(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            logger.info("prowpt-mcp HTTP transport ready")
            yield

    resource_metadata_url = f"{api_url.rstrip('/')}/.well-known/oauth-protected-resource"

    middleware = [
        Middleware(_McpPathNormaliser),
        Middleware(
            _BearerAuthMiddleware,
            resource_metadata_url=resource_metadata_url,
            require_auth=require_auth,
        ),
    ]

    app = Starlette(
        debug=False,
        routes=[
            Route("/healthz", endpoint=_healthz, methods=["GET"]),
            Mount("/mcp", app=handle_streamable_http),
        ],
        middleware=middleware,
        lifespan=lifespan,
    )
    # Skip the auto "/mcp" -> "/mcp/" redirect; _McpPathNormaliser handles it.
    app.router.redirect_slashes = False
    return app


def run_http(mcp_server, *, host: str, port: int, api_url: str,
             require_auth: bool = True,
             stateless: bool = True,
             json_response: bool = False,
             log_level: str = "info") -> None:
    """Run the MCP HTTP transport with uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError(
            "The HTTP transport requires uvicorn and starlette. "
            "Install with: pip install 'prowpt-mcp-server[http]'"
        ) from exc

    app = build_asgi_app(
        mcp_server,
        api_url=api_url,
        require_auth=require_auth,
        stateless=stateless,
        json_response=json_response,
    )
    uvicorn.run(app, host=host, port=port, log_level=log_level)
