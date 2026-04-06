"""Project management MCP tools."""
from __future__ import annotations
import json
import re
import uuid
from typing import Any
from prowpt_mcp.client import ProwptClient


def _slugify(name: str) -> str:
    """Convert a project name to a URL-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    if not slug:
        slug = "project"
    slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    return slug


async def list_projects(client: ProwptClient) -> str:
    """List all projects owned by the authenticated user."""
    data = await client.get("/api/projects")
    projects = data if isinstance(data, list) else data.get("projects", data)
    summary = []
    for p in (projects if isinstance(projects, list) else []):
        summary.append({
            "id": p.get("id"),
            "name": p.get("name"),
            "slug": p.get("slug"),
            "app_kind": p.get("app_kind"),
            "status": p.get("status"),
            "has_pending_changes": p.get("has_pending_changes"),
        })
    return json.dumps(summary, indent=2)


async def get_project(client: ProwptClient, project_id: int) -> str:
    """Get detailed information about a specific project."""
    data = await client.get(f"/api/projects/{project_id}")
    return json.dumps(data, indent=2, default=str)


async def create_project(client: ProwptClient, name: str, description: str = "") -> str:
    """Create a new code-based project."""
    data = await client.post("/api/projects", json={
        "name": name,
        "slug": _slugify(name),
        "description": description,
        "app_kind": "code",
    })
    return json.dumps(data, indent=2, default=str)


async def update_project(client: ProwptClient, project_id: int, **kwargs: Any) -> str:
    """Update project properties (name, description, settings)."""
    data = await client.patch(f"/api/projects/{project_id}", json=kwargs)
    return json.dumps(data, indent=2, default=str)


async def delete_project(client: ProwptClient, project_id: int) -> str:
    """Delete a project permanently."""
    status_code = await client.delete(f"/api/projects/{project_id}")
    return f"Project {project_id} deleted (HTTP {status_code})"


async def clone_project(client: ProwptClient, project_id: int) -> str:
    """Clone an existing project."""
    data = await client.post(f"/api/projects/{project_id}/clone")
    return json.dumps(data, indent=2, default=str)


async def publish_project(client: ProwptClient, project_id: int) -> str:
    """Publish the current draft to live."""
    data = await client.post(f"/api/projects/{project_id}/publish")
    return json.dumps(data, indent=2, default=str)


async def deploy_project(client: ProwptClient, project_id: int) -> str:
    """Deploy project to hosting."""
    data = await client.post(f"/api/projects/{project_id}/deploy")
    return json.dumps(data, indent=2, default=str)


async def get_deployments(client: ProwptClient, project_id: int) -> str:
    """Get deployment history for a project."""
    data = await client.get(f"/api/projects/{project_id}/deployments")
    return json.dumps(data, indent=2, default=str)


async def get_project_context(client: ProwptClient, project_id: int, include_sources: bool = False) -> str:
    """Get full project context for writing correct code."""
    params = "?include_sources=true" if include_sources else ""
    data = await client.get(f"/api/projects/{project_id}/context{params}")
    return json.dumps(data, indent=2, default=str)
