"""Stripe Connect / Payments MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def connect_stripe(client: ProwptClient, project_id: int, return_url: str) -> str:
    """Start Stripe Connect onboarding for a project. Returns the onboarding URL."""
    data = await client.post(
        f"/api/projects/{project_id}/payments/stripe/connect",
        params={"return_url": return_url},
    )
    return json.dumps(data, indent=2, default=str)


async def get_stripe_status(client: ProwptClient, project_id: int) -> str:
    """Check whether a project has a connected Stripe account."""
    data = await client.get(f"/api/projects/{project_id}/payments/stripe/status")
    return json.dumps(data, indent=2, default=str)


async def disconnect_stripe(client: ProwptClient, project_id: int) -> str:
    """Remove the Stripe Connect link from a project."""
    data = await client.post(f"/api/projects/{project_id}/payments/stripe/disconnect")
    return json.dumps(data, indent=2, default=str)
