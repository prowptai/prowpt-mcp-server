"""Built-in assistant proxy MCP tools.

On the stdio transport ``send_prompt`` keeps its historical synchronous
behaviour because desktop clients (Cursor, Claude Code) have no per-request
timeout and users expect a single tool call to return the final result.

On the Streamable HTTP transport the cloud connectors (Claude.ai, ChatGPT
Apps) kill tool calls around 30-60 s, which is far shorter than a full app
generation. In that mode ``send_prompt`` kicks the run off via
``POST /api/generate/start-async``, returns the ``run_id`` immediately, and
callers poll ``get_assistant_status(run_id=...)`` until the run terminates.
"""
from __future__ import annotations
import asyncio
import json
import httpx
from prowpt_mcp.client import ProwptClient
from prowpt_mcp.request_context import get_bearer_token

GENERATION_TIMEOUT = 300.0


def _is_http_transport() -> bool:
    """True when the tool call arrived over the HTTP transport.

    The HTTP transport always populates a per-request bearer token via
    :mod:`prowpt_mcp.request_context`; stdio leaves it unset (auth there
    comes from ``PROWPT_API_KEY`` on the environment).
    """
    return get_bearer_token() is not None


async def send_prompt(client: ProwptClient, project_id: int, prompt: str,
                       output_kind: str = "code",
                       auto_accept: bool = True) -> str:
    """
    Send a natural-language prompt to the Prowpt built-in AI assistant.

    The assistant analyses the project, plans changes, and applies them.
    This uses Prowpt's AI credits.

    Transport-aware behaviour:

    - stdio: runs synchronously; on timeout falls back to polling project
      sources so the caller still sees the completed result.
    - HTTP (remote connectors): kicks the run off asynchronously and returns
      a ``run_id`` immediately so the connector's short tool-call timeout
      doesn't kill an in-flight generation. Poll ``get_assistant_status``
      with the returned ``run_id`` until ``status`` is ``completed`` or
      ``failed``.
    """
    body = {
        "project_id": project_id,
        "prompt": prompt,
        "output_kind": output_kind,
        "preview_mode": not auto_accept,
        "auto_accept": auto_accept,
        "confirmed_complex": True,
    }

    if _is_http_transport():
        data = await client.post("/api/generate/start-async", json=body)
        result = {
            "run_id": data.get("run_id"),
            "status": data.get("status", "queued"),
            "project_id": data.get("project_id", project_id),
            "poll_with": "get_assistant_status",
            "hint": (
                "Generation kicked off. Call get_assistant_status("
                f"project_id={project_id}, run_id=\"{data.get('run_id')}\") "
                "and keep polling until status is 'completed' or 'failed'. "
                "Expect 30-180 s for typical edits, up to 300 s for the "
                "initial generation."
            ),
        }
        return json.dumps(result, indent=2, default=str)

    try:
        data = await client.post_with_timeout(
            "/api/generate/sync", json=body, timeout=GENERATION_TIMEOUT,
        )
        return _format_result(data)
    except httpx.ReadTimeout:
        pass

    result = await _poll_for_completion(client, project_id, max_wait=300)
    return result


async def _poll_for_completion(client: ProwptClient, project_id: int,
                                max_wait: int = 300) -> str:
    """Poll the project sources until generation finishes or timeout."""
    start_files = set()
    try:
        src = await client.get(f"/api/projects/{project_id}/sources")
        start_files = set((src.get("files") or {}).keys())
    except Exception:
        pass

    elapsed = 0
    interval = 5
    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval

        try:
            active = await client.get("/api/generate/runs/active",
                                       params={"project_id": project_id})
            if active is None or active == "null":
                src = await client.get(f"/api/projects/{project_id}/sources")
                current_files = set((src.get("files") or {}).keys())
                if current_files != start_files or current_files:
                    return json.dumps({
                        "message": "Generation completed (detected via polling).",
                        "files_changed": sorted(current_files),
                        "credits_used": None,
                    }, indent=2)
        except Exception:
            pass

    return json.dumps({
        "message": "Generation may still be running. Check project sources.",
        "timeout": True,
    }, indent=2)


def _format_result(data: dict) -> str:
    result = {
        "message": data.get("message"),
        "preview": data.get("preview"),
        "preview_token": data.get("preview_token"),
        "files_changed": list((data.get("files") or {}).keys()),
        "credits_used": data.get("credits_used"),
        "submitted_edits_succeeded": data.get("submitted_edits_succeeded"),
        "clarification_requested": data.get("clarification_requested"),
        "suggested_next_steps": data.get("suggested_next_steps"),
    }
    return json.dumps(result, indent=2, default=str)


async def accept_preview(client: ProwptClient, project_id: int,
                          preview_token: str) -> str:
    """Accept pending AI-generated changes and commit them to project sources."""
    data = await client.patch(f"/api/projects/{project_id}/sources", json={
        "preview_token": preview_token,
    })
    return json.dumps(data, indent=2, default=str)


async def get_assistant_status(client: ProwptClient, project_id: int,
                                run_id: str | None = None) -> str:
    """Check the status of an assistant generation run.

    When ``run_id`` is provided (the typical case for HTTP connectors after a
    ``send_prompt`` kickoff), looks up that specific run and returns its
    current ``status`` plus, once terminal, the full ``result_payload`` and
    ``preview_token``. Status values: ``running`` | ``completed`` | ``failed``
    | ``expired``.

    When ``run_id`` is omitted, falls back to the latest unacknowledged run
    for the project (legacy desktop behaviour).
    """
    if run_id:
        data = await client.get(f"/api/generate/runs/{run_id}")
        compact = {
            "run_id": data.get("run_id"),
            "status": data.get("status"),
            "project_id": data.get("project_id"),
            "preview_token": data.get("preview_token"),
            "credits_charged": data.get("credits_charged"),
            "error_detail": data.get("error_detail"),
        }
        payload = data.get("result_payload")
        if isinstance(payload, dict):
            compact["message"] = payload.get("message")
            files = payload.get("files")
            if isinstance(files, dict):
                compact["files_changed"] = sorted(files.keys())
            compact["submitted_edits_succeeded"] = payload.get("submitted_edits_succeeded")
            compact["suggested_next_steps"] = payload.get("suggested_next_steps")
            compact["clarification_requested"] = payload.get("clarification_requested")
        return json.dumps(compact, indent=2, default=str)

    data = await client.get("/api/generate/runs/active", params={
        "project_id": project_id,
    })
    return json.dumps(data, indent=2, default=str)
