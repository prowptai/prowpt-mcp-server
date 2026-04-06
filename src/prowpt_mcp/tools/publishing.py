"""Publishing and deployment MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def get_publish_status(client: ProwptClient, project_id: int) -> str:
    """Get the current publish/deploy status of a project."""
    data = await client.get(f"/api/projects/{project_id}")
    status_info = {
        "status": data.get("status"),
        "has_pending_changes": data.get("has_pending_changes"),
        "published_at": data.get("published_at"),
        "subdomain": data.get("subdomain"),
        "app_kind": data.get("app_kind"),
    }
    return json.dumps(status_info, indent=2, default=str)


async def discard_draft_changes(client: ProwptClient, project_id: int) -> str:
    """Discard unpublished draft changes, reverting to last published state."""
    data = await client.post(f"/api/projects/{project_id}/discard-draft-changes")
    return json.dumps(data, indent=2, default=str)


async def export_project(client: ProwptClient, project_id: int) -> str:
    """Export project as JSON backup."""
    data = await client.get(f"/api/projects/{project_id}/export")
    return json.dumps(data, indent=2, default=str)
