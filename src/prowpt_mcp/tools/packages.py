"""Package management MCP tools — catalog browsing and per-project dependencies."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def list_catalog(client: ProwptClient) -> str:
    """List all available npm packages in the platform catalog."""
    data = await client.get("/api/packages/catalog")
    return json.dumps(data, indent=2, default=str)


async def list_project_packages(client: ProwptClient, project_id: int) -> str:
    """List packages enabled for a specific project, with update availability."""
    data = await client.get(f"/api/projects/{project_id}/packages")
    return json.dumps(data, indent=2, default=str)


async def add_package(client: ProwptClient, project_id: int, package_name: str) -> str:
    """Add a catalog package to a project's dependency list."""
    data = await client.post(f"/api/projects/{project_id}/packages", json={
        "package_name": package_name,
    })
    return json.dumps(data, indent=2, default=str)


async def remove_package(client: ProwptClient, project_id: int, package_name: str) -> str:
    """Remove a package from a project (core packages cannot be removed)."""
    await client.delete(f"/api/projects/{project_id}/packages/{package_name}")
    return json.dumps({"status": "removed", "package_name": package_name})
