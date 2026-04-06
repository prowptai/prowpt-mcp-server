"""Source code management MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def list_source_files(client: ProwptClient, project_id: int) -> str:
    """List all source file paths in a project."""
    data = await client.get(f"/api/projects/{project_id}/sources")
    files = data.get("files", {}) if isinstance(data, dict) else {}
    return json.dumps(list(files.keys()), indent=2)


async def read_source_file(client: ProwptClient, project_id: int, file_path: str) -> str:
    """Read the content of a specific source file."""
    data = await client.get(f"/api/projects/{project_id}/sources")
    files = data.get("files", {}) if isinstance(data, dict) else {}
    content = files.get(file_path)
    if content is None:
        available = list(files.keys())
        count = len(available)
        return f"File not found: {file_path}. Project has {count} file(s). Use list_source_files to see available paths."
    return content


async def write_source_files(client: ProwptClient, project_id: int,
                              files: dict[str, str], entry_point: str | None = None) -> str:
    """
    Write or update one or more source files (merges with existing).

    Args:
        files: dict mapping file path to file content
        entry_point: optional entry point file (defaults to existing)
    """
    existing = await client.get(f"/api/projects/{project_id}/sources")
    existing_files = existing.get("files", {}) if isinstance(existing, dict) else {}
    merged = {**existing_files, **files}
    body: dict = {"files": merged}
    if entry_point:
        body["entry_point"] = entry_point
    data = await client.patch(f"/api/projects/{project_id}/sources", json=body)
    return json.dumps(data, indent=2, default=str)


async def get_preview_url(client: ProwptClient, project_id: int) -> str:
    """Build a preview bundle and return the URL to view it."""
    data = await client.post(f"/api/projects/{project_id}/preview-bundle-url")
    return json.dumps(data, indent=2, default=str)


async def get_source_versions(client: ProwptClient, project_id: int) -> str:
    """List source version history."""
    data = await client.get(f"/api/projects/{project_id}/source-versions")
    return json.dumps(data, indent=2, default=str)


async def restore_source_version(client: ProwptClient, project_id: int,
                                  version_id: int) -> str:
    """Restore project source to a previous version."""
    data = await client.post(
        f"/api/projects/{project_id}/source-versions/{version_id}/restore"
    )
    return json.dumps(data, indent=2, default=str)
