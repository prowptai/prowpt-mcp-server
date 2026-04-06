"""Translation / i18n MCP tools."""
from __future__ import annotations
import json
from prowpt_mcp.client import ProwptClient


async def get_translations(client: ProwptClient, project_id: int) -> str:
    """Get all translations for a project (all locales).

    Translations are stored in `project.app_translations` as
    ``{ key: { lang: value, ... }, ... }``.
    """
    data = await client.get(f"/api/projects/{project_id}")
    app_translations = data.get("app_translations") or {}
    enabled_languages = data.get("enabled_languages") or []
    default_language = data.get("default_language") or "en"
    return json.dumps({
        "enabled_languages": enabled_languages,
        "default_language": default_language,
        "translations": app_translations,
    }, indent=2, default=str)


async def update_translations(client: ProwptClient, project_id: int,
                                locale: str, translations: dict) -> str:
    """
    Update translations for a specific locale.

    Merges the provided keys into the existing ``app_translations`` map
    for the given locale, preserving other locales and keys.

    Args:
        locale: Language code (e.g. "en", "pt", "es")
        translations: Key-value pairs of translation strings
    """
    project = await client.get(f"/api/projects/{project_id}")
    existing = project.get("app_translations") or {}
    if not isinstance(existing, dict):
        existing = {}

    for key, value in translations.items():
        if key not in existing:
            existing[key] = {}
        if not isinstance(existing[key], dict):
            existing[key] = {}
        existing[key][locale] = value

    data = await client.patch(f"/api/projects/{project_id}", json={
        "app_translations": existing,
    })
    updated = data.get("app_translations") or existing
    return json.dumps({
        "locale": locale,
        "keys_updated": len(translations),
        "translations": updated,
    }, indent=2, default=str)
