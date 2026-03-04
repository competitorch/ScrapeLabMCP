"""Recipe database — site bundle folders for scraping recipes (shared across all users).

Each site gets its own folder under src/data/sites/{slug}/ with:
  - config.json   → metadata + scraping strategy
  - prompt.md     → extraction instructions for the LLM
  - script.py     → executable scraping/parsing code (optional)
  - schema.json   → output schema (optional)
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

SITES_DIR = Path(__file__).parent / "data" / "sites"

_recipes: List[Dict[str, Any]] = []


def _slugify(name: str) -> str:
    """Generate a clean folder name from site_name."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_config(site_dir: Path) -> Optional[Dict[str, Any]]:
    """Load config.json from a site bundle."""
    config_path = site_dir / "config.json"
    if not config_path.exists():
        return None
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["_dir"] = str(site_dir)
        config["_slug"] = site_dir.name
        return config
    except (json.JSONDecodeError, OSError):
        return None


def _save_config(site_dir: Path, config: Dict[str, Any]):
    """Save config.json to a site bundle."""
    site_dir.mkdir(parents=True, exist_ok=True)
    # Don't persist internal fields
    clean = {k: v for k, v in config.items() if not k.startswith("_")}
    (site_dir / "config.json").write_text(
        json.dumps(clean, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _load_all() -> List[Dict[str, Any]]:
    """Scan all site bundles and load configs."""
    if not SITES_DIR.exists():
        return []
    recipes = []
    for site_dir in sorted(SITES_DIR.iterdir()):
        if site_dir.is_dir():
            config = _load_config(site_dir)
            if config:
                recipes.append(config)
    return recipes


def _extract_domain(url: str) -> str:
    """Extract domain + path from URL for matching."""
    clean = re.sub(r"https?://", "", url).replace("www.", "")
    return clean.rstrip("/")


def _next_id() -> int:
    """Get next available ID."""
    if not _recipes:
        return 1
    return max(r.get("id", 0) for r in _recipes) + 1


def _load_file(site_dir: Path, filename: str) -> str:
    """Load a text file from a site bundle. Returns empty string if missing."""
    path = Path(site_dir) / filename
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _save_file(site_dir: Path, filename: str, content: str):
    """Save a text file to a site bundle."""
    Path(site_dir).mkdir(parents=True, exist_ok=True)
    (Path(site_dir) / filename).write_text(content, encoding="utf-8")


def _delete_dir(site_dir: Path):
    """Delete a site bundle directory."""
    import shutil
    if site_dir.exists():
        shutil.rmtree(site_dir)


# --- Public API (async interface for compatibility with server.py) ---


async def init_db():
    """Load all site bundles. Call once at server startup."""
    global _recipes
    SITES_DIR.mkdir(parents=True, exist_ok=True)
    _recipes = _load_all()


async def close_db():
    """No-op — site bundles are saved on each write."""
    pass


async def match_recipe(url: str) -> Optional[Dict[str, Any]]:
    """Find a recipe matching the given URL. Loads prompt and script from files."""
    url_clean = _extract_domain(url)
    best = None
    for r in _recipes:
        pattern = r.get("site_pattern", "")
        if pattern in url_clean or url_clean in pattern:
            if best is None or r.get("times_used", 0) > best.get("times_used", 0):
                best = r
    if best is None:
        return None

    # Hydrate: load prompt, script, schema from files
    site_dir = Path(best["_dir"])
    result = dict(best)
    result["prompt"] = _load_file(site_dir, "prompt.md")
    result["script"] = _load_file(site_dir, "script.py")
    schema_str = _load_file(site_dir, "schema.json")
    if schema_str:
        try:
            result["schema"] = json.loads(schema_str)
        except json.JSONDecodeError:
            result["schema"] = None
    else:
        result["schema"] = None
    return result


async def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a site bundle. Upserts on site_pattern."""
    pattern = data["site_pattern"]
    site_name = data.get("site_name", pattern)
    slug = _slugify(site_name)
    site_dir = SITES_DIR / slug

    # Extract file contents from data
    prompt = data.pop("prompt", None)
    script = data.pop("script", None)
    schema = data.pop("schema", None)

    # Check if exists (by pattern)
    existing = None
    for r in _recipes:
        if r.get("site_pattern") == pattern:
            existing = r
            site_dir = Path(r["_dir"])  # Use existing directory
            break

    if existing:
        # Update existing
        existing.update({
            "site_name": data.get("site_name", existing.get("site_name")),
            "scrape_level": data.get("scrape_level", existing.get("scrape_level", 2)),
            "wait_for": data.get("wait_for"),
            "needs_proxy": data.get("needs_proxy", 0),
            "geo_target": data.get("geo_target"),
            "api_endpoints": data.get("api_endpoints"),
            "pagination": data.get("pagination"),
            "updated_at": datetime.utcnow().isoformat(),
        })
        _save_config(site_dir, existing)
        recipe_id = existing["id"]
        created = False
    else:
        # Create new
        config = {
            "id": _next_id(),
            "site_pattern": pattern,
            "site_name": site_name,
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
        _save_config(site_dir, config)
        config["_dir"] = str(site_dir)
        config["_slug"] = slug
        _recipes.append(config)
        recipe_id = config["id"]
        created = True

    # Save file contents
    if prompt:
        _save_file(site_dir, "prompt.md", prompt)
    if script:
        _save_file(site_dir, "script.py", script)
    if schema:
        schema_str = json.dumps(schema, indent=2, ensure_ascii=False) if isinstance(schema, dict) else schema
        _save_file(site_dir, "schema.json", schema_str)

    result = {"id": recipe_id, "slug": slug, "created": created, "updated": not created}
    files = []
    if prompt:
        files.append("prompt.md")
    if script:
        files.append("script.py")
    if schema:
        files.append("schema.json")
    if files:
        result["files_saved"] = files
    return result


async def list_recipes() -> List[Dict[str, Any]]:
    """List all recipes ordered by usage. Includes file availability info."""
    recipes = sorted(_recipes, key=lambda r: r.get("times_used", 0), reverse=True)
    result = []
    for r in recipes:
        entry = {k: v for k, v in r.items() if not k.startswith("_")}
        site_dir = Path(r["_dir"])
        entry["slug"] = r.get("_slug", "")
        entry["has_prompt"] = (site_dir / "prompt.md").exists()
        entry["has_script"] = (site_dir / "script.py").exists()
        entry["has_schema"] = (site_dir / "schema.json").exists()
        result.append(entry)
    return result


async def delete_recipe(recipe_id: int) -> bool:
    """Delete a site bundle by recipe ID."""
    global _recipes
    for r in _recipes:
        if r.get("id") == recipe_id:
            site_dir = Path(r["_dir"])
            _delete_dir(site_dir)
            _recipes = [x for x in _recipes if x.get("id") != recipe_id]
            return True
    return False


async def increment_usage(recipe_id: int):
    """Increment times_used for a recipe."""
    for r in _recipes:
        if r.get("id") == recipe_id:
            r["times_used"] = r.get("times_used", 0) + 1
            _save_config(Path(r["_dir"]), r)
            break
