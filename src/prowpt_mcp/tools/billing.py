"""Billing and credits MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def get_usage(client: ProwptClient) -> str:
    """Get current usage: credits, projects, workflows, domains."""
    data = await client.get("/api/billing/usage")
    return json.dumps(data, indent=2, default=str)


async def get_credits(client: ProwptClient) -> str:
    """Get current credit balance."""
    data = await client.get("/api/billing/credits")
    return json.dumps(data, indent=2, default=str)


async def purchase_credit_pack(client: ProwptClient, credits: int = 10) -> str:
    """
    Purchase credits. Returns a Stripe checkout URL.

    Args:
        credits: Number of credits to purchase (minimum 5)
    """
    data = await client.post("/api/billing/create-credit-pack-checkout", json={
        "credits": credits,
    })
    return json.dumps(data, indent=2, default=str)


async def get_account_info(client: ProwptClient) -> str:
    """Get current user account info, tier, and limits."""
    data = await client.get("/api/auth/me")
    return json.dumps(data, indent=2, default=str)
