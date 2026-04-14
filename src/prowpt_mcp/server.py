"""
Prowpt.ai MCP server entry point.

Exposes the Prowpt REST API as MCP tools and resources so AI agents
(Cursor, Claude Code, OpenClaw, etc.) can manage web apps programmatically.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource

from prowpt_mcp.config import get_api_key, get_api_url
from prowpt_mcp.client import ProwptClient
from prowpt_mcp.tools import projects, sources, assistant, records, workflows, publishing, billing, assets, translations, email_templates, payments, packages

server = Server("prowpt")

_client: ProwptClient | None = None


def _get_client() -> ProwptClient:
    global _client
    if _client is None:
        _client = ProwptClient(get_api_url(), get_api_key())
    return _client


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[Tool] = [
    # --- Projects ---
    Tool(name="list_projects", description="List all projects owned by the authenticated user", inputSchema={"type": "object", "properties": {}, "required": []}),
    Tool(name="get_project", description="Get detailed information about a specific project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer", "description": "Project ID"}}, "required": ["project_id"]}),
    Tool(name="create_project", description="Create a new web app project", inputSchema={"type": "object", "properties": {"name": {"type": "string", "description": "Project name"}, "description": {"type": "string", "description": "Project description", "default": ""}}, "required": ["name"]}),
    Tool(name="update_project", description="Update project name, description, or settings", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "name": {"type": "string"}, "description": {"type": "string"}}, "required": ["project_id"]}),
    Tool(name="delete_project", description="Delete a project permanently", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="clone_project", description="Clone an existing project. Provide a new name; slug is auto-generated if omitted.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer", "description": "ID of the project to clone"}, "name": {"type": "string", "description": "Name for the cloned project (defaults to '<source name> — Copy')"}, "slug": {"type": "string", "description": "URL slug for the clone (auto-generated from name if omitted)"}}, "required": ["project_id"]}),
    Tool(name="publish_project", description="Publish the current draft to live (makes the app accessible via subdomain)", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="deploy_project", description="Deploy project to hosting", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="get_deployments", description="Get deployment history for a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),

    # --- Source code ---
    Tool(name="list_source_files", description="List all source file paths in a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="read_source_file", description="Read the content of a specific source file", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "file_path": {"type": "string", "description": "File path (e.g. 'App.tsx')"}}, "required": ["project_id", "file_path"]}),
    Tool(name="write_source_files", description="Write or update one or more source files", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "files": {"type": "object", "description": "Map of file path to content", "additionalProperties": {"type": "string"}}, "entry_point": {"type": "string", "description": "Optional entry point file"}}, "required": ["project_id", "files"]}),
    Tool(name="get_preview_url", description="Build a preview bundle and return the URL", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="get_source_versions", description="List source version history", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="restore_source_version", description="Restore project source to a previous version", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "version_id": {"type": "integer"}}, "required": ["project_id", "version_id"]}),

    # --- Built-in assistant ---
    Tool(name="send_prompt", description="Send a natural-language prompt to the Prowpt AI assistant to modify the app (uses Prowpt AI credits). Initial generation may take up to 5 minutes; subsequent updates are faster.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "prompt": {"type": "string", "description": "Natural language instruction (e.g. 'Add a contact form')"}, "auto_accept": {"type": "boolean", "description": "Auto-commit changes", "default": True}}, "required": ["project_id", "prompt"]}),
    Tool(name="accept_preview", description="Accept pending AI-generated changes", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "preview_token": {"type": "string"}}, "required": ["project_id", "preview_token"]}),
    Tool(name="get_assistant_status", description="Check if a generation run is active", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),

    # --- Record types and records ---
    Tool(name="list_record_types", description="List all record types for a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="create_record_type", description="Create a new record type with field definitions. Each field needs {name, type}; label is auto-generated from name if omitted. select/multiselect options: use a plain string array (e.g. [\"Small\",\"Medium\",\"Large\"]); {label,value} objects are also accepted and auto-normalized. user_scope='profile' for one-per-user data (upsert /me/profile-records/) or 'collection' for many-per-user (CRUD with Bearer).", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "name": {"type": "string"}, "slug": {"type": "string"}, "fields": {"type": "array", "items": {"type": "object", "description": "Field object: {name, type, label? (auto from name), required?, options? (string[]), default_value?, reference_to?, placeholder?}"}}, "user_scope": {"type": "string", "enum": ["profile", "collection"], "description": "User scoping: 'profile' = one record per user (upsert), 'collection' = many records per user (CRUD). Omit for global/shared record types."}, "is_user_profile": {"type": "boolean", "description": "Deprecated — use user_scope instead. True is equivalent to user_scope='profile'."}, "description": {"type": "string"}, "display_name_field": {"type": "string", "description": "Field name used as label in lists"}, "show_in_backoffice": {"type": "boolean", "description": "Show in backoffice UI (default true)"}}, "required": ["project_id", "name", "slug", "fields"]}),
    Tool(name="update_record_type", description="Update a record type's name, slug, fields, or other settings", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "record_type_id": {"type": "integer"}, "name": {"type": "string"}, "slug": {"type": "string"}, "fields": {"type": "array", "items": {"type": "object"}}, "user_scope": {"type": "string", "enum": ["profile", "collection"], "description": "User scoping: 'profile' = one per user, 'collection' = many per user. Set to null to remove user scoping."}, "is_user_profile": {"type": "boolean"}, "description": {"type": "string"}, "display_name_field": {"type": "string"}, "show_in_backoffice": {"type": "boolean"}}, "required": ["project_id", "record_type_id"]}),
    Tool(name="list_records", description="List records of a specific type", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "record_type_slug": {"type": "string"}}, "required": ["project_id", "record_type_slug"]}),
    Tool(name="create_record", description="Create a new record", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "record_type_slug": {"type": "string"}, "fields": {"type": "object"}}, "required": ["project_id", "record_type_slug", "fields"]}),
    Tool(name="update_record", description="Update an existing record", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "record_type_slug": {"type": "string"}, "record_id": {"type": "integer"}, "fields": {"type": "object"}}, "required": ["project_id", "record_type_slug", "record_id", "fields"]}),
    Tool(name="delete_record", description="Delete a record", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "record_type_slug": {"type": "string"}, "record_id": {"type": "integer"}}, "required": ["project_id", "record_type_slug", "record_id"]}),

    # --- Workflows ---
    Tool(name="list_workflows", description="List all workflows for a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="create_workflow", description="Create a workflow. Trigger types: form_submit, button_click, cron, chat_message, webhook (inbound HTTP), stripe_event. IMPORTANT node structure: each node needs type='action' (or 'condition'/'loop') with the specific action inside action.type. Example node: {\"id\": \"n1\", \"type\": \"action\", \"action\": {\"type\": \"send_email\", \"config\": {\"to\": \"...\", \"subject\": \"...\", \"body\": \"...\"}}, \"next_node_id\": null}. Action types: send_email, http_request, llm_chat, save_record, fetch_data, send_whatsapp, redirect, forward_to_human, send_reply. Node outputs propagate via {{nodes.<id>.body}}.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "name": {"type": "string"}, "definition": {"type": "object", "description": "Workflow definition with trigger, entry_node_id, and nodes array. Each node: {id, type:'action'|'condition'|'loop', action:{type, config}, next_node_id}"}}, "required": ["project_id", "name", "definition"]}),
    Tool(name="update_workflow", description="Update a workflow's name, definition, or enabled status", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "integer"}, "name": {"type": "string"}, "definition": {"type": "object"}}, "required": ["workflow_id"]}),
    Tool(name="delete_workflow", description="Delete a workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "integer"}}, "required": ["workflow_id"]}),
    Tool(name="execute_workflow", description="Execute a workflow with trigger data", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "integer"}, "trigger_data": {"type": "object"}}, "required": ["workflow_id"]}),
    Tool(name="get_workflow_executions", description="Get execution history for a workflow", inputSchema={"type": "object", "properties": {"workflow_id": {"type": "integer"}}, "required": ["workflow_id"]}),

    # --- Publishing ---
    Tool(name="get_publish_status", description="Get current publish/deploy status", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="discard_draft_changes", description="Discard unpublished draft changes", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="export_project", description="Export project as JSON backup", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),

    # --- Assets ---
    Tool(name="list_assets", description="List project assets (images, files)", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="upload_asset", description="Upload an asset to a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "filename": {"type": "string"}, "content_base64": {"type": "string", "description": "Base64-encoded file content"}, "content_type": {"type": "string", "default": "image/png"}}, "required": ["project_id", "filename", "content_base64"]}),
    Tool(name="delete_asset", description="Delete an asset", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "filename": {"type": "string"}}, "required": ["project_id", "filename"]}),

    # --- Translations ---
    Tool(name="get_translations", description="Get all translations for a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="update_translations", description="Update translations for a locale", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "locale": {"type": "string", "description": "Language code (e.g. 'en', 'pt')"}, "translations": {"type": "object"}}, "required": ["project_id", "locale", "translations"]}),

    # --- Email templates ---
    Tool(name="list_email_templates", description="List all email templates for a project (system and custom)", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="get_email_template", description="Get a specific email template by slug, including full HTML body and variables schema", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "slug": {"type": "string", "description": "Template slug (e.g. 'welcome', 'password-reset')"}}, "required": ["project_id", "slug"]}),
    Tool(name="upsert_email_template", description="Create or update an email template. For new templates 'name' is required. System templates only allow editing subject, body_html, body_text, and variables_schema.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "slug": {"type": "string", "description": "Template slug (lowercase, hyphens/underscores allowed)"}, "name": {"type": "string", "description": "Display name (required for new templates)"}, "category": {"type": "string", "description": "Category (e.g. 'auth', 'notification', 'marketing', 'custom')"}, "subject": {"type": "string", "description": "Email subject line (supports {{variable}} placeholders)"}, "body_html": {"type": "string", "description": "HTML email body (supports {{variable}} placeholders)"}, "body_text": {"type": "string", "description": "Plain-text fallback body"}, "variables_schema": {"type": "array", "items": {"type": "object", "properties": {"key": {"type": "string"}, "label": {"type": "string"}, "sample": {"type": "string"}}}, "description": "Variable definitions with sample values for preview"}}, "required": ["project_id", "slug"]}),
    Tool(name="delete_email_template", description="Delete a custom email template. System templates cannot be deleted.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "slug": {"type": "string"}}, "required": ["project_id", "slug"]}),
    Tool(name="preview_email_template", description="Render a preview of an email template with optional sample context variables", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "slug": {"type": "string"}, "context": {"type": "object", "description": "Variable values to substitute in the template"}}, "required": ["project_id", "slug"]}),
    Tool(name="send_test_email", description="Send a test email using a template to a specified address", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "slug": {"type": "string"}, "to_email": {"type": "string", "description": "Recipient email address"}, "context": {"type": "object", "description": "Variable values to substitute in the template"}}, "required": ["project_id", "slug", "to_email"]}),
    Tool(name="seed_email_templates", description="Seed default email templates for a project (inserts factory defaults, skips existing slugs)", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="reset_system_templates", description="Reset all system email templates to their factory defaults (overwrites customisations)", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),

    # --- Packages / Dependencies ---
    Tool(name="list_catalog", description="List all npm packages available in the platform catalog (not project-specific)", inputSchema={"type": "object", "properties": {}, "required": []}),
    Tool(name="list_project_packages", description="List npm packages enabled for a project, with version info and update availability", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="add_package", description="Add a catalog package to a project's dependencies. The package must exist in the platform catalog.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "package_name": {"type": "string", "description": "Package name from the catalog (e.g. 'recharts', 'zustand')"}}, "required": ["project_id", "package_name"]}),
    Tool(name="remove_package", description="Remove a package from a project's dependencies. Core packages (react, react-dom, etc.) cannot be removed.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "package_name": {"type": "string"}}, "required": ["project_id", "package_name"]}),

    # --- Project context (for writing code) ---
    Tool(name="get_project_context", description="IMPORTANT: Call this BEFORE writing code for a project. Returns full conventions, patterns, record types, templates, packages, and rules that the generated code MUST follow.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer", "description": "Project ID"}, "include_sources": {"type": "boolean", "description": "Include full source file contents (can be large)", "default": False}}, "required": ["project_id"]}),

    # --- Billing ---
    Tool(name="get_usage", description="Get current usage (credits, projects, workflows, domains)", inputSchema={"type": "object", "properties": {}, "required": []}),
    Tool(name="get_credits", description="Get current credit balance", inputSchema={"type": "object", "properties": {}, "required": []}),
    Tool(name="purchase_credit_pack", description="Purchase credits (returns Stripe checkout URL). Minimum 5 credits.", inputSchema={"type": "object", "properties": {"credits": {"type": "integer", "minimum": 5, "default": 10, "description": "Number of credits to purchase (minimum 5)"}}, "required": []}),
    Tool(name="get_account_info", description="Get current user account info, tier, and limits", inputSchema={"type": "object", "properties": {}, "required": []}),

    # --- Payments (Stripe Connect) ---
    Tool(name="connect_stripe", description="Start Stripe Connect onboarding for a project (returns onboarding URL). Requires Starter+ tier.", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}, "return_url": {"type": "string", "description": "URL to redirect to after onboarding"}}, "required": ["project_id", "return_url"]}),
    Tool(name="get_stripe_status", description="Check whether a project has a connected Stripe account", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
    Tool(name="disconnect_stripe", description="Remove the Stripe Connect link from a project", inputSchema={"type": "object", "properties": {"project_id": {"type": "integer"}}, "required": ["project_id"]}),
]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    # Projects
    "list_projects": lambda c, a: projects.list_projects(c),
    "get_project": lambda c, a: projects.get_project(c, a["project_id"]),
    "create_project": lambda c, a: projects.create_project(c, a["name"], a.get("description", "")),
    "update_project": lambda c, a: projects.update_project(c, a.pop("project_id"), **a),
    "delete_project": lambda c, a: projects.delete_project(c, a["project_id"]),
    "clone_project": lambda c, a: projects.clone_project(c, a["project_id"], a.get("name"), a.get("slug")),
    "publish_project": lambda c, a: projects.publish_project(c, a["project_id"]),
    "deploy_project": lambda c, a: projects.deploy_project(c, a["project_id"]),
    "get_deployments": lambda c, a: projects.get_deployments(c, a["project_id"]),
    "get_project_context": lambda c, a: projects.get_project_context(c, a["project_id"], a.get("include_sources", False)),
    # Sources
    "list_source_files": lambda c, a: sources.list_source_files(c, a["project_id"]),
    "read_source_file": lambda c, a: sources.read_source_file(c, a["project_id"], a["file_path"]),
    "write_source_files": lambda c, a: sources.write_source_files(c, a["project_id"], a["files"], a.get("entry_point")),
    "get_preview_url": lambda c, a: sources.get_preview_url(c, a["project_id"]),
    "get_source_versions": lambda c, a: sources.get_source_versions(c, a["project_id"]),
    "restore_source_version": lambda c, a: sources.restore_source_version(c, a["project_id"], a["version_id"]),
    # Assistant
    "send_prompt": lambda c, a: assistant.send_prompt(c, a["project_id"], a["prompt"], "code", a.get("auto_accept", True)),
    "accept_preview": lambda c, a: assistant.accept_preview(c, a["project_id"], a["preview_token"]),
    "get_assistant_status": lambda c, a: assistant.get_assistant_status(c, a["project_id"]),
    # Records
    "list_record_types": lambda c, a: records.list_record_types(c, a["project_id"]),
    "create_record_type": lambda c, a: records.create_record_type(c, a["project_id"], a["name"], a["slug"], a["fields"], user_scope=a.get("user_scope"), is_user_profile=a.get("is_user_profile", False), description=a.get("description"), display_name_field=a.get("display_name_field"), show_in_backoffice=a.get("show_in_backoffice", True)),
    "update_record_type": lambda c, a: records.update_record_type(c, a.pop("project_id"), a.pop("record_type_id"), **a),
    "list_records": lambda c, a: records.list_records(c, a["project_id"], a["record_type_slug"]),
    "create_record": lambda c, a: records.create_record(c, a["project_id"], a["record_type_slug"], a["fields"]),
    "update_record": lambda c, a: records.update_record(c, a["project_id"], a["record_type_slug"], a["record_id"], a["fields"]),
    "delete_record": lambda c, a: records.delete_record(c, a["project_id"], a["record_type_slug"], a["record_id"]),
    # Workflows
    "list_workflows": lambda c, a: workflows.list_workflows(c, a["project_id"]),
    "create_workflow": lambda c, a: workflows.create_workflow(c, a["project_id"], a["name"], a["definition"]),
    "update_workflow": lambda c, a: workflows.update_workflow(c, a.pop("workflow_id"), **a),
    "delete_workflow": lambda c, a: workflows.delete_workflow(c, a["workflow_id"]),
    "execute_workflow": lambda c, a: workflows.execute_workflow(c, a["workflow_id"], a.get("trigger_data")),
    "get_workflow_executions": lambda c, a: workflows.get_workflow_executions(c, a["workflow_id"]),
    # Publishing
    "get_publish_status": lambda c, a: publishing.get_publish_status(c, a["project_id"]),
    "discard_draft_changes": lambda c, a: publishing.discard_draft_changes(c, a["project_id"]),
    "export_project": lambda c, a: publishing.export_project(c, a["project_id"]),
    # Assets
    "list_assets": lambda c, a: assets.list_assets(c, a["project_id"]),
    "upload_asset": lambda c, a: assets.upload_asset(c, a["project_id"], a["filename"], a["content_base64"], a.get("content_type", "image/png")),
    "delete_asset": lambda c, a: assets.delete_asset(c, a["project_id"], a["filename"]),
    # Translations
    "get_translations": lambda c, a: translations.get_translations(c, a["project_id"]),
    "update_translations": lambda c, a: translations.update_translations(c, a["project_id"], a["locale"], a["translations"]),
    # Email templates
    "list_email_templates": lambda c, a: email_templates.list_email_templates(c, a["project_id"]),
    "get_email_template": lambda c, a: email_templates.get_email_template(c, a["project_id"], a["slug"]),
    "upsert_email_template": lambda c, a: email_templates.upsert_email_template(c, a.pop("project_id"), slug=a.pop("slug"), **a),
    "delete_email_template": lambda c, a: email_templates.delete_email_template(c, a["project_id"], a["slug"]),
    "preview_email_template": lambda c, a: email_templates.preview_email_template(c, a["project_id"], a["slug"], a.get("context")),
    "send_test_email": lambda c, a: email_templates.send_test_email(c, a["project_id"], a["slug"], a["to_email"], a.get("context")),
    "seed_email_templates": lambda c, a: email_templates.seed_email_templates(c, a["project_id"]),
    "reset_system_templates": lambda c, a: email_templates.reset_system_templates(c, a["project_id"]),
    # Packages
    "list_catalog": lambda c, a: packages.list_catalog(c),
    "list_project_packages": lambda c, a: packages.list_project_packages(c, a["project_id"]),
    "add_package": lambda c, a: packages.add_package(c, a["project_id"], a["package_name"]),
    "remove_package": lambda c, a: packages.remove_package(c, a["project_id"], a["package_name"]),
    # Billing
    "get_usage": lambda c, a: billing.get_usage(c),
    "get_credits": lambda c, a: billing.get_credits(c),
    "purchase_credit_pack": lambda c, a: billing.purchase_credit_pack(c, a.get("credits", 10)),
    "get_account_info": lambda c, a: billing.get_account_info(c),
    # Payments
    "connect_stripe": lambda c, a: payments.connect_stripe(c, a["project_id"], a["return_url"]),
    "get_stripe_status": lambda c, a: payments.get_stripe_status(c, a["project_id"]),
    "disconnect_stripe": lambda c, a: payments.disconnect_stripe(c, a["project_id"]),
}


# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = _DISPATCH.get(name)
    if handler is None:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]
    try:
        client = _get_client()
        result = await handler(client, arguments)
        return [TextContent(type="text", text=result)]
    except Exception as e:
        return [TextContent(type="text", text=_safe_error(e))]


def _safe_error(exc: Exception) -> str:
    """Return a user-safe error string, stripping internal/server details."""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            body = exc.response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
        except Exception:
            detail = None

        if status == 401:
            return "Error: Authentication failed. Check your PROWPT_API_KEY."
        if status == 403:
            return f"Error: Forbidden — {detail or 'you do not have access to this resource'}."
        if status == 404:
            return f"Error: Not found — {detail or 'the requested resource does not exist'}."
        if status == 422:
            if isinstance(detail, list):
                msgs = [f"{e.get('loc', ['?'])[-1]}: {e.get('msg', '?')}" for e in detail]
                return f"Error: Validation failed — {'; '.join(msgs)}"
            return f"Error: Validation failed — {detail or 'check your parameters'}."
        if status == 429:
            return "Error: Rate limit exceeded. Please wait and try again."
        if status in (502, 503, 504):
            return f"Error: Service temporarily unavailable (HTTP {status}). Try again in a moment."
        return f"Error: Request failed (HTTP {status}){f' — {detail}' if detail and isinstance(detail, str) else ''}."

    if isinstance(exc, httpx.TimeoutException):
        return "Error: Request timed out. The operation may still be running — check status before retrying."

    if isinstance(exc, (httpx.ConnectError, httpx.NetworkError)):
        return "Error: Could not connect to the Prowpt API. Check your network and PROWPT_API_URL."

    if isinstance(exc, KeyError):
        return f"Error: Missing required parameter: {exc}"

    if isinstance(exc, RuntimeError) and "PROWPT_API_KEY" in str(exc):
        return str(exc)

    return f"Error: {type(exc).__name__}: An unexpected error occurred. Please try again."


@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return [
        Resource(uri="prowpt://docs/quickstart", name="Prowpt Quickstart Guide",
                 description="Getting started with the Prowpt MCP server",
                 mimeType="text/plain"),
        Resource(uri="prowpt://docs/code-guidelines", name="Code Quality Guidelines",
                 description="Guidelines for generated React/TypeScript code",
                 mimeType="text/plain"),
    ]


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    if uri == "prowpt://docs/quickstart":
        return _QUICKSTART_DOC
    if uri == "prowpt://docs/code-guidelines":
        return _CODE_GUIDELINES_DOC
    return f"Unknown resource: {uri}"


_QUICKSTART_DOC = """\
# Prowpt.ai MCP Server — Quickstart

## Setup

1. Create an API key at https://prowpt.ai/settings → API Keys
2. Install: pip install prowpt-mcp-server (or pipx install prowpt-mcp-server)
3. Configure in your AI tool:

   Cursor (.cursor/mcp.json):
   {
     "mcpServers": {
       "prowpt": {
         "command": "prowpt-mcp",
         "env": { "PROWPT_API_KEY": "pk_live_..." }
       }
     }
   }

## Common workflows

### Create and deploy a new app
1. create_project(name="My App")
2. write_source_files(project_id=X, files={"App.tsx": "..."})
3. publish_project(project_id=X)

### Use the built-in AI assistant
1. send_prompt(project_id=X, prompt="Add a contact form with validation")
   (This uses Prowpt AI credits)

### Manage data
1. create_record_type(project_id=X, name="Products", slug="products", fields=[...])
2. create_record_type(project_id=X, name="User Prefs", slug="user-prefs", fields=[...], user_scope="profile")
3. create_record_type(project_id=X, name="Tracking Entries", slug="tracking-entries", fields=[...], user_scope="collection")
4. create_record(project_id=X, record_type_slug="products", fields={...})

### Manage dependencies
1. list_catalog()  → see all available npm packages
2. list_project_packages(project_id=X)  → see what's enabled
3. add_package(project_id=X, package_name="recharts")  → enable a package
4. remove_package(project_id=X, package_name="recharts")  → disable

### Workflows
1. create_workflow(project_id=X, name="Welcome Email", definition={...})
2. execute_workflow(workflow_id=Y, trigger_data={...})
"""

_CODE_GUIDELINES_DOC = """\
# Prowpt Code Conventions & Best Practices

IMPORTANT: For project-specific context (record types, workflows, translations,
enabled features), always call `get_project_context(project_id)` first.
This document covers platform-wide conventions.

## Stack
- React 18+ with TypeScript (strict)
- Tailwind CSS for all styling
- React Router v6 (HashRouter — injected by the build, see below)
- 2-space indentation, functional components with hooks

## Critical Build Rules
1. **Do NOT add any router provider** (BrowserRouter, MemoryRouter, HashRouter).
   The Prowpt build system wraps the app in a HashRouter automatically.
2. Keep exactly **one `export default`** in the entry point file (usually App.tsx).
3. **Only import npm packages enabled for the project.** The build will fail for
   unknown imports. Call `list_project_packages` to see what's available, or
   `get_project_context` which includes the package list.
   Core packages (always available): react, react-dom, react-router-dom, dompurify.
   Additional packages from the platform catalog (date-fns, lucide-react, recharts,
   zustand, zod, framer-motion, sonner, etc.) can be enabled per-project via
   `add_package` or Project Settings → Dependencies.

## window.__PROJECT_CONFIG__
Every published Prowpt app has `window.__PROJECT_CONFIG__` injected at runtime:
```ts
interface ProjectConfig {
  projectSlug: string;
  project_id: number;
  enabled_languages: string[];  // e.g. ["en", "pt"]
  default_language: string;     // e.g. "en"
  apiBaseUrl: string;           // usually ""
  analytics?: { enabled: boolean; require_consent: boolean; ... };
}
```
Always use `window.__PROJECT_CONFIG__.projectSlug` — never hardcode slugs.

## API Base URL Pattern
All API calls must use same-origin URLs:
```ts
const cfg = (window as any).__PROJECT_CONFIG__;
const base = (cfg?.apiBaseUrl || '') + '/api/public/' + cfg?.projectSlug;
```
Never hardcode `https://prowpt.ai` or another host.

## Records (Data) API
```
GET    {base}/records/{slug}                → { items: [...], total, limit, offset }
POST   {base}/records/{slug}                → body: { data: { field: value } }
PATCH  {base}/records/{slug}/{id}           → body: { data: { field: value } }
DELETE {base}/records/{slug}/{id}
```
- Response is NOT an array — always use `response.items` for the list.
- Field values live inside `item.data` (e.g. `item.data.title`), not at top level.
- For richtext fields: sanitize with DOMPurify before dangerouslySetInnerHTML.
- For asset fields: the API rewrites paths so `<img src={item.data.image} />` works.

### User-Scoped Records (user_scope)
Record types can be scoped to the logged-in user via `user_scope`:

**`user_scope: "profile"`** — One record per user (preferences, settings, subscription):
```
GET    {base}/me/profile-records/{slug}       → { items: [...], total } (Bearer required)
POST   {base}/me/profile-records/{slug}       → body: { data: {...} } (Bearer required)
       Creates the record if none exists, updates if it does (upsert).
```
Always use the POST upsert for profile data instead of PATCH.

**`user_scope: "collection"`** — Many records per user (entries, orders, notes):
```
GET    {base}/records/{slug}                  → { items: [...], total } (Bearer required — auto-filtered by user)
POST   {base}/records/{slug}                  → body: { data: {...} } (Bearer required — auto-associates user)
PATCH  {base}/records/{slug}/{id}             → body: { data: {...} } (Bearer required)
DELETE {base}/records/{slug}/{id}             (Bearer required)
```

`is_user_profile: true` (without `user_scope`) is still accepted and treated as `user_scope: "profile"`.

### Field Types
- `select` / `multiselect` with `"options": ["A", "B"]` for fixed value sets
- `reference` / `reference_list` with `"reference_to": "target-slug"` to link records
- `asset` — project-managed images (uploaded by owner or AI-generated)
- `file` — user-uploaded content (photos, documents) via the public upload API
- `text`, `textarea`, `richtext`, `number`, `email`, `phone`, `date`, `datetime`, `boolean`, `url`, `json`

## Translations (i18n)
- Use `useTranslations()` hook from `./useTranslations.ts` (template available)
- Call: `const { t, language, setLanguage } = useTranslations();`
- Use `t("key.name")` in JSX for UI strings
- **NEVER** use `t()` at module scope or in top-level arrays
- **NEVER** import react-i18next or i18next
- Translation API: `GET /api/public/{slug}/translations?lang={locale}`
- Key format: dot-notation (e.g. `hero.title`, `nav.home`, `footer.copyright`)
- Only translate UI text (buttons, headings, labels), NOT data arrays

## Authentication
- JWT Bearer auth via `AuthContext.tsx` (template available)
- Login: `POST /api/public/app-auth/{slug}/login` body: `{ email, password }`
- Signup: `POST /api/public/app-auth/{slug}/signup` body: `{ email, password, name? }`
- Profile: `GET /api/public/app-auth/{slug}/me` (with Bearer token)
- Token stored in `localStorage` — NOT cookies
- Login/signup routes must be OUTSIDE the main layout (no sidebar on auth pages)

## Analytics & Consent
- Analytics tracking is injected automatically by the platform.
- Do NOT add analytics/tracking/GTM code.
- For cookie consent UI, use the `CookieConsent.tsx` template.
- It communicates with `window.__prowptAnalytics` (injected at runtime).

## Design
- Web-first responsive design (mobile-friendly)
- Semantic HTML, ARIA labels, keyboard navigation
- Loading states and error boundaries
- Props interfaces for all components
"""


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

async def _run_stdio():
    async with stdio_server() as (read_stream, write_stream):
        init_options = server.create_initialization_options()
        await server.run(read_stream, write_stream, init_options)


def main():
    parser = argparse.ArgumentParser(description="Prowpt.ai MCP server")
    parser.add_argument("--api-key", help="Prowpt API key (or set PROWPT_API_KEY env)")
    parser.add_argument("--api-url", help="Prowpt API URL (or set PROWPT_API_URL env)")
    args = parser.parse_args()

    if args.api_key:
        os.environ["PROWPT_API_KEY"] = args.api_key
    if args.api_url:
        os.environ["PROWPT_API_URL"] = args.api_url

    import asyncio
    asyncio.run(_run_stdio())


if __name__ == "__main__":
    main()
