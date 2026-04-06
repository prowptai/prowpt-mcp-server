"""Workflow management MCP tools."""
from __future__ import annotations
import json
from typing import Any
from prowpt_mcp.client import ProwptClient


async def list_workflows(client: ProwptClient, project_id: int) -> str:
    """List all workflows for a project."""
    data = await client.get(f"/api/workflows/project/{project_id}")
    return json.dumps(data, indent=2, default=str)


async def create_workflow(client: ProwptClient, project_id: int,
                           name: str, definition: dict) -> str:
    """Create a new workflow with a JSON definition."""
    data = await client.post(f"/api/workflows/project/{project_id}", json={
        "name": name,
        "definition": definition,
    })
    return json.dumps(data, indent=2, default=str)


async def update_workflow(client: ProwptClient, workflow_id: int, **kwargs: Any) -> str:
    """Update a workflow's name, definition, or enabled status."""
    data = await client.patch(f"/api/workflows/{workflow_id}", json=kwargs)
    return json.dumps(data, indent=2, default=str)


async def delete_workflow(client: ProwptClient, workflow_id: int) -> str:
    """Delete a workflow."""
    status_code = await client.delete(f"/api/workflows/{workflow_id}")
    return f"Workflow {workflow_id} deleted (HTTP {status_code})"


async def execute_workflow(client: ProwptClient, workflow_id: int,
                            trigger_data: dict | None = None) -> str:
    """Execute a workflow with optional trigger data."""
    data = await client.post(f"/api/workflows/{workflow_id}/execute", json={
        "trigger_data": trigger_data or {},
    })
    return json.dumps(data, indent=2, default=str)


async def get_workflow_executions(client: ProwptClient, workflow_id: int) -> str:
    """Get execution history for a workflow."""
    data = await client.get(f"/api/workflows/{workflow_id}/executions")
    return json.dumps(data, indent=2, default=str)
