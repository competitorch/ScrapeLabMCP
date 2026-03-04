"""Recipe database — JSON file + markdown prompts for scraping recipes (shared across all users)."""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Recipes stored in repo so they're shared across all MCP users
DATA_DIR = Path(__file__).parent / "data"
RECIPES_PATH = DATA_DIR / "recipes.json"
PROMPTS_DIR = DATA_DIR / "prompts"

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


def _prompt_filename(site_name: str) -> str:
    """Generate a clean filename from site_name: lowercase, hyphens, .md."""
    clean = re.sub(r"[^a-z0-9]+", "-", site_name.lower()).strip("-")
    return f"{clean}.md"


def _load_prompt(recipe: Dict[str, Any]) -> str:
    """Load the prompt markdown for a recipe. Returns empty string if no prompt file."""
    prompt_file = recipe.get("prompt_file")
    if not prompt_file:
        return ""
    path = PROMPTS_DIR / prompt_file
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _save_prompt(prompt_file: str, content: str):
    """Save prompt markdown to file."""
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    (PROMPTS_DIR / prompt_file).write_text(content, encoding="utf-8")


def _delete_prompt(prompt_file: str):
    """Delete prompt file if it exists."""
    path = PROMPTS_DIR / prompt_file
    if path.exists():
        path.unlink()


async def init_db():
    """Load recipes from JSON file. Call once at server startup."""
    global _recipes
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    _recipes = _load()


async def close_db():
    """Save recipes to disk. Call at server shutdown."""
    _save()


async def match_recipe(url: str) -> Optional[Dict[str, Any]]:
    """Find a recipe matching the given URL's domain. Loads prompt from file."""
    domain = _extract_domain(url)
    best = None
    for r in _recipes:
        pattern = r.get("site_pattern", "")
        if pattern in domain or domain in pattern:
            if best is None or r.get("times_used", 0) > best.get("times_used", 0):
                best = r
    if best is None:
        return None
    # Attach prompt content from markdown file
    result = dict(best)
    result["prompt"] = _load_prompt(best)
    return result


async def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a recipe. Upserts on site_pattern. Saves prompt to separate .md file."""
    pattern = data["site_pattern"]
    site_name = data.get("site_name", pattern)
    prompt_content = data.pop("prompt", None)

    # Determine prompt filename
    prompt_file = _prompt_filename(site_name) if prompt_content else None

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
            if prompt_content:
                # Use existing prompt_file name or generate new
                pf = r.get("prompt_file") or _prompt_filename(site_name)
                r["prompt_file"] = pf
                _save_prompt(pf, prompt_content)
            _save()
            return {"id": r["id"], "updated": True, "prompt_file": r.get("prompt_file")}

    # Create new
    recipe = {
        "id": _next_id(),
        "site_pattern": pattern,
        "site_name": site_name,
        "scrape_level": data.get("scrape_level", 2),
        "wait_for": data.get("wait_for"),
        "needs_proxy": data.get("needs_proxy", 0),
        "geo_target": data.get("geo_target"),
        "api_endpoints": data.get("api_endpoints"),
        "pagination": data.get("pagination"),
        "prompt_file": prompt_file,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "times_used": 0,
        "success_rate": 0.0,
    }
    _recipes.append(recipe)
    if prompt_content and prompt_file:
        _save_prompt(prompt_file, prompt_content)
    _save()
    return {"id": recipe["id"], "created": True, "prompt_file": prompt_file}


async def list_recipes() -> List[Dict[str, Any]]:
    """List all recipes ordered by usage."""
    return sorted(_recipes, key=lambda r: r.get("times_used", 0), reverse=True)


async def delete_recipe(recipe_id: int) -> bool:
    """Delete a recipe by ID. Also removes the prompt file."""
    global _recipes
    for r in _recipes:
        if r.get("id") == recipe_id:
            pf = r.get("prompt_file")
            if pf:
                _delete_prompt(pf)
            _recipes = [x for x in _recipes if x.get("id") != recipe_id]
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
