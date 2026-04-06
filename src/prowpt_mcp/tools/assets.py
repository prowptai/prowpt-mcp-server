"""Asset management MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def list_assets(client: ProwptClient, project_id: int) -> str:
    """List all assets (images, files) in a project."""
    data = await client.get(f"/api/projects/{project_id}/assets")
    return json.dumps(data, indent=2, default=str)


async def upload_asset(client: ProwptClient, project_id: int,
                        filename: str, content_base64: str,
                        content_type: str = "image/png") -> str:
    """
    Upload an asset to a project.

    Args:
        filename: Target filename (e.g. "logo.png")
        content_base64: Base64-encoded file content
        content_type: MIME type
    """
    import base64
    file_bytes = base64.b64decode(content_base64)
    data = await client.post_form(
        f"/api/projects/{project_id}/assets/upload",
        files={"file": (filename, file_bytes, content_type)},
    )
    return json.dumps(data, indent=2, default=str)


async def delete_asset(client: ProwptClient, project_id: int, filename: str) -> str:
    """Delete an asset from a project."""
    status_code = await client.delete(
        f"/api/projects/{project_id}/assets/{filename}"
    )
    return f"Asset '{filename}' deleted (HTTP {status_code})"
