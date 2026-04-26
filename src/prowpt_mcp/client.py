"""HTTP client wrapper for the Prowpt.ai REST API."""
from __future__ import annotations

import asyncio
import httpx
from typing import Any, Optional

_RETRYABLE_CODES = frozenset({502, 503, 504})
_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 0.8


class ProwptClient:
    """Thin wrapper around httpx that injects credentials as headers.

    ``api_key`` is sent as ``X-API-Key``. If ``bearer_token`` is provided
    instead (used by the HTTP transport, where the caller authenticates with
    an OAuth-issued JWT or an API key passed in ``Authorization: Bearer``),
    it is forwarded verbatim. Exactly one of ``api_key`` / ``bearer_token``
    should be set.
    """

    def __init__(self, api_url: str, api_key: str = "", *,
                 bearer_token: str = "", timeout: float = 120.0):
        self._base = api_url.rstrip("/")
        hdrs: dict[str, str] = {"Content-Type": "application/json"}
        if bearer_token:
            hdrs["Authorization"] = f"Bearer {bearer_token}"
        else:
            hdrs["X-API-Key"] = api_key
        self._headers = hdrs
        self._timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self._base}{path}"

    async def _request(self, method: str, path: str, *,
                       json: Any = None, params: dict | None = None,
                       headers: dict | None = None, files: dict | None = None,
                       data: dict | None = None,
                       timeout: float | None = None,
                       retry: bool = True) -> httpx.Response:
        """Execute a request with automatic retry on transient server errors."""
        hdrs = headers if headers is not None else self._headers
        t = timeout or self._timeout
        max_attempts = (_MAX_RETRIES + 1) if retry else 1

        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))
            try:
                async with httpx.AsyncClient(timeout=t) as c:
                    r = await c.request(
                        method, self._url(path),
                        headers=hdrs, json=json, params=params,
                        files=files, data=data,
                    )
                if retry and r.status_code in _RETRYABLE_CODES and attempt < _MAX_RETRIES:
                    last_exc = httpx.HTTPStatusError(
                        f"HTTP {r.status_code}", request=r.request, response=r
                    )
                    continue
                r.raise_for_status()
                return r
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt >= _MAX_RETRIES:
                    raise
                continue
        raise last_exc  # type: ignore[misc]

    async def get(self, path: str, params: dict | None = None) -> Any:
        r = await self._request("GET", path, params=params)
        return r.json()

    async def post(self, path: str, json: Any = None, params: dict | None = None) -> Any:
        r = await self._request("POST", path, json=json, params=params)
        return r.json()

    async def post_with_timeout(self, path: str, json: Any = None,
                                 timeout: float = 120.0) -> Any:
        """POST with a custom timeout (raises httpx.ReadTimeout on expiry)."""
        r = await self._request("POST", path, json=json, timeout=timeout, retry=False)
        return r.json()

    async def put(self, path: str, json: Any = None) -> Any:
        r = await self._request("PUT", path, json=json)
        return r.json()

    async def patch(self, path: str, json: Any = None) -> Any:
        r = await self._request("PATCH", path, json=json)
        return r.json()

    async def delete(self, path: str) -> int:
        r = await self._request("DELETE", path)
        return r.status_code

    async def post_form(self, path: str, files: dict, data: dict | None = None) -> Any:
        hdrs = {k: v for k, v in self._headers.items() if k != "Content-Type"}
        r = await self._request(
            "POST", path, headers=hdrs, files=files, data=data or {},
        )
        return r.json()
