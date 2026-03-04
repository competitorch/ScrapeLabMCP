"""Knowledge loader — prompts and schemas for the scraping intelligence layer."""

import json
from pathlib import Path
from typing import Dict

_BASE = Path(__file__).parent

# --- Specialist recipes (markdown prompts) ---

SPECIALIST_DEFS = {
    "api-rest": "REST API patterns",
    "api-graphql": "GraphQL patterns",
    "dom-playwright": "DOM scraping with browser",
    "ecommerce": "Shopify, WooCommerce, Magento",
    "frameworks": "Next.js, Nuxt, Remix, Gatsby",
    "wordpress": "WordPress REST API",
}


def _load_text(directory: str, filename: str) -> str:
    path = _BASE / directory / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


# Pre-load at import time
specialists: Dict[str, dict] = {}
for _name, _description in SPECIALIST_DEFS.items():
    specialists[_name] = {
        "description": _description,
        "content": _load_text("prompts", f"{_name}.md"),
    }

agent_workflow: str = _load_text("prompts", "agent.md")

schemas: Dict[str, str] = {}
_schemas_dir = _BASE / "schemas"
if _schemas_dir.exists():
    for _path in _schemas_dir.glob("*.json"):
        schemas[_path.stem] = _path.read_text(encoding="utf-8")

VALID_SPECIALISTS = list(SPECIALIST_DEFS.keys())
VALID_SCHEMAS = list(schemas.keys())
