"""Project email template MCP tools."""
from __future__ import annotations

import json
from typing import Any, Optional

from prowpt_mcp.client import ProwptClient


async def list_email_templates(client: ProwptClient, project_id: int) -> str:
    """List all email templates for a project."""
    data = await client.get(f"/api/projects/{project_id}/email-templates")
    return json.dumps(data, indent=2, default=str)


async def get_email_template(client: ProwptClient, project_id: int,
                              slug: str) -> str:
    """Get a specific email template by slug, including full HTML body."""
    data = await client.get(f"/api/projects/{project_id}/email-templates/{slug}")
    return json.dumps(data, indent=2, default=str)


async def upsert_email_template(client: ProwptClient, project_id: int,
                                 slug: str, **fields: Any) -> str:
    """Create or update an email template.

    For new templates ``name`` is required.  For existing system templates
    only ``subject``, ``body_html``, ``body_text``, and ``variables_schema``
    can be changed.
    """
    body: dict[str, Any] = {}
    for key in ("name", "category", "subject", "body_html", "body_text", "variables_schema"):
        if key in fields and fields[key] is not None:
            body[key] = fields[key]
    data = await client.put(f"/api/projects/{project_id}/email-templates/{slug}", json=body)
    return json.dumps(data, indent=2, default=str)


async def delete_email_template(client: ProwptClient, project_id: int,
                                 slug: str) -> str:
    """Delete a custom email template. System templates cannot be deleted."""
    status_code = await client.delete(
        f"/api/projects/{project_id}/email-templates/{slug}"
    )
    return f"Email template '{slug}' deleted (HTTP {status_code})"


async def preview_email_template(client: ProwptClient, project_id: int,
                                  slug: str,
                                  context: Optional[dict] = None) -> str:
    """Render a preview of an email template with optional sample context variables."""
    body: dict[str, Any] = {}
    if context:
        body["context"] = context
    data = await client.post(
        f"/api/projects/{project_id}/email-templates/{slug}/preview", json=body
    )
    return json.dumps(data, indent=2, default=str)


async def send_test_email(client: ProwptClient, project_id: int,
                           slug: str, to_email: str,
                           context: Optional[dict] = None) -> str:
    """Send a test email using a template to the given address."""
    body: dict[str, Any] = {"to_email": to_email}
    if context:
        body["context"] = context
    data = await client.post(
        f"/api/projects/{project_id}/email-templates/{slug}/send-test", json=body
    )
    return json.dumps(data, indent=2, default=str)


async def seed_email_templates(client: ProwptClient, project_id: int) -> str:
    """Seed default email templates for a project (skips existing slugs)."""
    data = await client.post(
        f"/api/projects/{project_id}/email-templates/seed", json={}
    )
    return json.dumps(data, indent=2, default=str)


async def reset_system_templates(client: ProwptClient, project_id: int) -> str:
    """Reset all system email templates to their factory defaults."""
    data = await client.post(
        f"/api/projects/{project_id}/email-templates/reset-system", json={}
    )
    return json.dumps(data, indent=2, default=str)
