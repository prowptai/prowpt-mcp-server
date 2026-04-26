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
            await _send_401(
                send,
                self.resource_metadata_url,
                wants_html=_wants_html(scope),
                request_origin=_request_origin(scope),
            )
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


def _request_origin(scope: Scope) -> str | None:
    """Reconstruct ``scheme://host`` from the incoming request so the landing
    page advertises the URL the user actually navigated to.
    """
    host: str | None = None
    forwarded_proto: str | None = None
    for name, value in scope.get("headers") or []:
        if name == b"host":
            host = value.decode("latin-1", errors="ignore").strip()
        elif name == b"x-forwarded-proto":
            forwarded_proto = value.decode("latin-1", errors="ignore").strip().split(",")[0]
    if not host:
        return None
    scheme = forwarded_proto or scope.get("scheme") or "http"
    return f"{scheme}://{host}"


def _wants_html(scope: Scope) -> bool:
    """Return ``True`` when the request looks like a browser hitting the
    endpoint directly (``Accept: text/html`` and a ``GET`` method).

    MCP clients always negotiate JSON / SSE, so this never affects the
    discovery handshake.
    """
    if scope.get("method", "").upper() != "GET":
        return False
    for name, value in scope.get("headers") or []:
        if name == b"accept":
            accept = value.decode("latin-1", errors="ignore").lower()
            if "text/html" in accept:
                return True
            return False
    return False


_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Prowpt MCP server</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{ color-scheme: light dark; }}
  body {{
    margin: 0; padding: 3rem 1.5rem;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: #0a0a0a; color: #f5f5f5;
    display: flex; align-items: center; justify-content: center; min-height: 100vh;
  }}
  .card {{
    max-width: 560px; width: 100%; padding: 2.5rem;
    background: #111; border: 1px solid #262626; border-radius: 16px;
    box-shadow: 0 20px 50px rgba(0,0,0,0.4);
  }}
  h1 {{ margin: 0 0 .5rem; font-size: 1.6rem; }}
  .badge {{
    display: inline-block; padding: .15rem .55rem; margin-bottom: 1rem;
    background: #064e3b; color: #6ee7b7; border-radius: 999px;
    font-size: .75rem; letter-spacing: .04em; text-transform: uppercase;
  }}
  p  {{ line-height: 1.55; color: #d4d4d4; }}
  ul {{ padding-left: 1.2rem; line-height: 1.7; }}
  a  {{ color: #34d399; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  code {{
    background: #1f1f1f; padding: .15rem .4rem; border-radius: 4px;
    font-size: .9em;
  }}
  .foot {{ margin-top: 1.75rem; font-size: .85rem; color: #9ca3af; }}
</style>
</head>
<body>
  <main class="card">
    <span class="badge">MCP server</span>
    <h1>Prowpt.ai MCP server</h1>
    <p>This endpoint is for AI assistants — <strong>not for direct browser access</strong>.
    It speaks the <a href="https://modelcontextprotocol.io" target="_blank" rel="noopener">Model Context Protocol</a>
    over Streamable HTTP and is protected by OAuth 2.1.</p>
    <p>To connect Prowpt to your AI assistant, head to the setup page —
       it has a one-click copy of the URL and step-by-step instructions
       for Claude.ai, ChatGPT, Cursor, and SDK clients:</p>
    <p style="margin: 1.25rem 0;">
      <a href="{landing_url}"
         style="display:inline-block; background:#10b981; color:#fff;
                padding:.6rem 1.1rem; border-radius:8px; font-weight:600;
                text-decoration:none;">
        Open setup guide →
      </a>
    </p>
    <p style="font-size:.9rem; color:#a3a3a3;">
      Server URL: <code>{mcp_url}</code>
    </p>
    <p class="foot">Manage active connections in
       <a href="{settings_url}">Settings → API Keys</a>.
       Full reference: <a href="{docs_url}">/docs/agent-integration</a>.
    </p>
  </main>
</body>
</html>
"""


async def _send_401(send: Send, resource_metadata_url: str, *,
                    wants_html: bool = False,
                    request_origin: str | None = None) -> None:
    challenge = (
        f'Bearer realm="prowpt", '
        f'resource_metadata="{resource_metadata_url}"'
    )

    if wants_html:
        api_origin = resource_metadata_url.split("/.well-known/")[0]
        if "//api." in api_origin:
            web_origin = api_origin.replace("//api.", "//", 1)
        else:
            web_origin = api_origin
        mcp_origin = request_origin or api_origin
        body = _LANDING_HTML.format(
            mcp_url=f"{mcp_origin}/mcp",
            landing_url=f"{web_origin}/mcp",
            settings_url=f"{web_origin}/settings",
            docs_url=f"{web_origin}/docs/agent-integration",
        ).encode("utf-8")
        content_type = b"text/html; charset=utf-8"
    else:
        body = b'{"error":"unauthorized","error_description":"Missing or invalid bearer token"}'
        content_type = b"application/json"

    await send({
        "type": "http.response.start",
        "status": 401,
        "headers": [
            (b"content-type", content_type),
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
