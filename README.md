# Prowpt.ai MCP Server

MCP (Model Context Protocol) server that lets AI agents create, edit, and publish web apps on Prowpt.ai.

## Setup

### 1. Get an API key

Go to [prowpt.ai/settings](https://prowpt.ai/settings) → API Keys → Create a new key with the scopes you need.

### 2. Install

```bash
pip install prowpt-mcp-server
# or
pipx install prowpt-mcp-server
```

### 3. Configure your AI tool

**Cursor** (`.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "prowpt": {
      "command": "prowpt-mcp",
      "env": {
        "PROWPT_API_KEY": "pk_live_your_key_here"
      }
    }
  }
}
```

**Claude Code**:

```bash
export PROWPT_API_KEY="pk_live_your_key_here"
prowpt-mcp
```

**Environment variables**:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `PROWPT_API_KEY` | Yes (stdio only) | — | Your Prowpt API key |
| `PROWPT_API_URL` | No | `https://api.prowpt.ai` | API base URL |

## Transports

The server supports two transports:

### stdio (default)

Used by local IDEs like Cursor and Claude Code. The CLI authenticates with the
`PROWPT_API_KEY` environment variable and speaks MCP over stdin/stdout.

```bash
prowpt-mcp                    # reads PROWPT_API_KEY from env
prowpt-mcp --api-key pk_...   # or pass explicitly
```

### Streamable HTTP (remote)

Used by public connectors (Claude.ai custom servers, ChatGPT Apps, etc.). The
server listens on an HTTP endpoint at `/mcp`; every request must carry an
`Authorization: Bearer <token>` header. The token is either a Prowpt API key
(`pk_live_...`) or — once the Prowpt OAuth AS is live — a JWT issued by
`https://prowpt.ai/oauth/*`. Tokens are forwarded verbatim to the Prowpt REST
API, which owns all scope/rate-limit enforcement.

```bash
pip install "prowpt-mcp-server[http]"
prowpt-mcp --transport http --bind 0.0.0.0:8001
```

Useful flags:

| Flag | Description |
|------|-------------|
| `--transport http` | Run the HTTP transport (default: `stdio`) |
| `--bind HOST:PORT` | Listen address (default: `0.0.0.0:8001`) |
| `--stateful` | Use session-state mode (default: stateless) |
| `--json-response` | Return plain JSON instead of SSE streams |
| `--no-auth` | Disable bearer-token auth (**local debugging only**) |
| `--api-url URL` | Prowpt REST API base URL |

The server also exposes `GET /healthz` for liveness probes. Unauthenticated
requests return `401` with a `WWW-Authenticate: Bearer` challenge pointing at
the OAuth protected-resource metadata URL, so MCP clients can auto-discover
the authorisation server.

OAuth-issued tokens (used by Claude.ai and ChatGPT directory connectors) are
short-lived JWTs backed by an `api_keys` row with `origin='oauth'`. Each
connector key carries a default rate limit of **20 requests per minute** and a
**25-credit per-UTC-day spend cap** for credit-consuming actions
(`send_prompt`, `/api/generate/*`). Users can revoke any connection from
*Settings → API Keys* in the Prowpt web app.

## Getting Started

After installation, the recommended first step for any code-generation task is to fetch the project context:

```
get_project_context(project_id=123)
```

This returns the full conventions, available record types, templates, i18n state, enabled packages, and subscription info for the project — everything the agent needs to write correct, Prowpt-compliant code.

The server also exposes two static resources that agents can read at any time:

| Resource URI | Description |
|-------------|-------------|
| `prowpt://docs/quickstart` | Quick-start guide with tool summaries |
| `prowpt://docs/code-guidelines` | Comprehensive code conventions: `PROJECT_CONFIG` shape, auth patterns, i18n, records API, routing rules, component templates, and best practices |

## Available Tools

### Project Management
- `list_projects` — List all projects
- `get_project` — Get project details
- `get_project_context` — Get full project context for writing correct code (stack, conventions, record types, templates, i18n state)
- `create_project` — Create a new app
- `update_project` — Update project settings
- `delete_project` — Delete a project
- `clone_project` — Clone a project
- `publish_project` — Publish to live
- `deploy_project` — Deploy to hosting

### Source Code
- `list_source_files` — List files in a project
- `read_source_file` — Read a file's content
- `write_source_files` — Write/update files
- `get_preview_url` — Get preview URL
- `get_source_versions` — Version history
- `restore_source_version` — Restore a version

### AI Assistant (uses Prowpt credits)
- `send_prompt` — Send instruction to Prowpt AI. Transport-aware: on **stdio** (Cursor / Claude Code) it blocks up to 5 minutes and returns the final result; on **HTTP** (remote connectors with short tool-call timeouts) it returns `{run_id, status: "queued"}` immediately and the caller polls `get_assistant_status(project_id, run_id=...)` until the run terminates.
- `accept_preview` — Accept AI changes
- `get_assistant_status` — Check generation status. Pass `run_id` to poll a specific async run (HTTP flow); omit it to fetch the latest active run for the project (stdio flow).

### Records & Data
- `list_record_types` / `create_record_type` / `update_record_type`
- `list_records` / `create_record` / `update_record` / `delete_record`

### Workflows
- `list_workflows` / `create_workflow` / `update_workflow` / `delete_workflow`
- `execute_workflow` / `get_workflow_executions`

### Packages / Dependencies
- `list_catalog` — Browse all available npm packages in the platform catalog
- `list_project_packages` — List packages enabled for a project (with update info)
- `add_package` — Enable a catalog package for a project
- `remove_package` — Remove a package from a project

### Assets
- `list_assets` / `upload_asset` / `delete_asset`

### Translations
- `get_translations` / `update_translations`

### Email Templates
- `list_email_templates` — List all templates (system + custom)
- `get_email_template` — Get a template by slug (full HTML body + variables)
- `upsert_email_template` — Create or update a template
- `delete_email_template` — Delete a custom template
- `preview_email_template` — Render a preview with sample variables
- `send_test_email` — Send a test email to a given address
- `seed_email_templates` — Seed factory defaults
- `reset_system_templates` — Reset system templates to defaults

### Payments (Stripe Connect)
- `connect_stripe` — Start Stripe Connect onboarding for a project
- `get_stripe_status` — Check Stripe connection status
- `disconnect_stripe` — Remove Stripe Connect link

### Billing
- `get_usage` / `get_credits` / `purchase_credit_pack` / `get_account_info`

## Development

```bash
cd prowpt-mcp-server
pip install -e .
prowpt-mcp --api-key pk_live_test_key --api-url http://localhost:8000
```

## License

MIT
