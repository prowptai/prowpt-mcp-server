"""Record types and records MCP tools."""
from __future__ import annotations
import json
from typing import Any
from prowpt_mcp.client import ProwptClient


async def list_record_types(client: ProwptClient, project_id: int) -> str:
    """List all record types defined for a project."""
    data = await client.get(f"/api/projects/{project_id}/record-types")
    return json.dumps(data, indent=2, default=str)


async def create_record_type(client: ProwptClient, project_id: int,
                               name: str, slug: str, fields: list[dict],
                               is_user_profile: bool = False,
                               description: str | None = None,
                               display_name_field: str | None = None,
                               show_in_backoffice: bool = True) -> str:
    """Create a new record type with field definitions."""
    payload: dict[str, Any] = {
        "name": name,
        "slug": slug,
        "fields": fields,
        "is_user_profile": is_user_profile,
        "show_in_backoffice": show_in_backoffice,
    }
    if description:
        payload["description"] = description
    if display_name_field:
        payload["display_name_field"] = display_name_field
    data = await client.post(f"/api/projects/{project_id}/record-types", json=payload)
    return json.dumps(data, indent=2, default=str)


async def update_record_type(client: ProwptClient, project_id: int,
                               record_type_id: int, **kwargs: Any) -> str:
    """Update a record type's name, slug, or fields."""
    data = await client.patch(
        f"/api/projects/{project_id}/record-types/{record_type_id}", json=kwargs
    )
    return json.dumps(data, indent=2, default=str)


async def list_records(client: ProwptClient, project_id: int,
                        record_type_slug: str) -> str:
    """List records of a specific type."""
    data = await client.get(
        f"/api/projects/{project_id}/records/{record_type_slug}"
    )
    return json.dumps(data, indent=2, default=str)


async def create_record(client: ProwptClient, project_id: int,
                          record_type_slug: str, fields: dict) -> str:
    """Create a new record."""
    data = await client.post(
        f"/api/projects/{project_id}/records/{record_type_slug}",
        json={"data": fields},
    )
    return json.dumps(data, indent=2, default=str)


async def update_record(client: ProwptClient, project_id: int,
                          record_type_slug: str, record_id: int, fields: dict) -> str:
    """Update an existing record."""
    data = await client.patch(
        f"/api/projects/{project_id}/records/{record_type_slug}/{record_id}",
        json={"data": fields},
    )
    return json.dumps(data, indent=2, default=str)


async def delete_record(client: ProwptClient, project_id: int,
                          record_type_slug: str, record_id: int) -> str:
    """Delete a record."""
    status_code = await client.delete(
        f"/api/projects/{project_id}/records/{record_type_slug}/{record_id}"
    )
    return f"Record {record_id} deleted (HTTP {status_code})"
