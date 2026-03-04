"""Recipe database — JSON file for scraping recipes (shared across all users)."""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Recipes stored in repo so they're shared across all MCP users
RECIPES_PATH = Path(__file__).parent / "data" / "recipes.json"

_recipes: List[Dict[str, Any]] = []


def _load() -> List[Dict[str, Any]]:
    """Load recipes from JSON file."""
    if not RECIPES_PATH.exists():
        return []
    try:
        return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save():
    """Write recipes to JSON file."""
    RECIPES_PATH.parent.mkdir(parents=True, exist_ok=True)
    RECIPES_PATH.write_text(
        json.dumps(_recipes, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _next_id() -> int:
    """Get next available ID."""
    if not _recipes:
        return 1
    return max(r.get("id", 0) for r in _recipes) + 1


def _extract_domain(url: str) -> str:
    """Extract domain from URL, stripping protocol and www."""
    return re.sub(r"https?://", "", url).split("/")[0].replace("www.", "")


async def init_db():
    """Load recipes from JSON file. Call once at server startup."""
    global _recipes
    RECIPES_PATH.parent.mkdir(parents=True, exist_ok=True)
    _recipes = _load()


async def close_db():
    """Save recipes to disk. Call at server shutdown."""
    _save()


async def match_recipe(url: str) -> Optional[Dict[str, Any]]:
    """Find a recipe matching the given URL's domain."""
    domain = _extract_domain(url)
    best = None
    for r in _recipes:
        pattern = r.get("site_pattern", "")
        if pattern in domain or domain in pattern:
            if best is None or r.get("times_used", 0) > best.get("times_used", 0):
                best = r
    return best


async def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a recipe. Upserts on site_pattern."""
    pattern = data["site_pattern"]

    # Check if exists
    for r in _recipes:
        if r.get("site_pattern") == pattern:
            r.update({
                "site_name": data.get("site_name", r.get("site_name")),
                "scrape_level": data.get("scrape_level", r.get("scrape_level", 2)),
                "wait_for": data.get("wait_for"),
                "needs_proxy": data.get("needs_proxy", 0),
                "geo_target": data.get("geo_target"),
                "api_endpoints": data.get("api_endpoints"),
                "pagination": data.get("pagination"),
                "updated_at": datetime.utcnow().isoformat(),
            })
            _save()
            return {"id": r["id"], "updated": True}

    # Create new
    recipe = {
        "id": _next_id(),
        "site_pattern": pattern,
        "site_name": data.get("site_name", ""),
        "scrape_level": data.get("scrape_level", 2),
        "wait_for": data.get("wait_for"),
        "needs_proxy": data.get("needs_proxy", 0),
        "geo_target": data.get("geo_target"),
        "api_endpoints": data.get("api_endpoints"),
        "pagination": data.get("pagination"),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "times_used": 0,
        "success_rate": 0.0,
    }
    _recipes.append(recipe)
    _save()
    return {"id": recipe["id"], "created": True}


async def list_recipes() -> List[Dict[str, Any]]:
    """List all recipes ordered by usage."""
    return sorted(_recipes, key=lambda r: r.get("times_used", 0), reverse=True)


async def delete_recipe(recipe_id: int) -> bool:
    """Delete a recipe by ID."""
    global _recipes
    before = len(_recipes)
    _recipes = [r for r in _recipes if r.get("id") != recipe_id]
    if len(_recipes) < before:
        _save()
        return True
    return False


async def increment_usage(recipe_id: int):
    """Increment times_used for a recipe."""
    for r in _recipes:
        if r.get("id") == recipe_id:
            r["times_used"] = r.get("times_used", 0) + 1
            _save()
            break
