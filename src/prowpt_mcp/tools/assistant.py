"""Built-in assistant proxy MCP tools."""
from __future__ import annotations
import asyncio
import json
import httpx
from prowpt_mcp.client import ProwptClient

GENERATION_TIMEOUT = 300.0


async def send_prompt(client: ProwptClient, project_id: int, prompt: str,
                       output_kind: str = "code",
                       auto_accept: bool = True) -> str:
    """
    Send a natural-language prompt to the Prowpt built-in AI assistant.

    The assistant analyses the project, plans changes, and applies them.
    This uses Prowpt's AI credits.

    If the sync endpoint times out (common for initial generation), falls back
    to polling the project sources until they change.
    """
    body = {
        "project_id": project_id,
        "prompt": prompt,
        "output_kind": output_kind,
        "preview_mode": not auto_accept,
        "auto_accept": auto_accept,
        "confirmed_complex": True,
    }

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


async def get_assistant_status(client: ProwptClient, project_id: int) -> str:
    """Check if a generation run is currently active for this project."""
    data = await client.get("/api/generate/runs/active", params={
        "project_id": project_id,
    })
    return json.dumps(data, indent=2, default=str)
