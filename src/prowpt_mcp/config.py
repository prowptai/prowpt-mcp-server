"""Configuration for the Prowpt MCP server."""
import os


def get_api_key() -> str:
    key = os.environ.get("PROWPT_API_KEY", "")
    if not key:
        raise RuntimeError(
            "PROWPT_API_KEY environment variable is required. "
            "Create one at https://prowpt.ai/settings → API Keys."
        )
    return key


def get_api_url() -> str:
    return os.environ.get("PROWPT_API_URL", "https://api.prowpt.ai")
