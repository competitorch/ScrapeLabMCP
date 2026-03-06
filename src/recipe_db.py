"""Recipe database — Supabase PostgREST backend for scraping recipes.

Uses the Supabase REST API (PostgREST) via httpx.
Tables: recipes, recipe_history (auto-populated by DB trigger on update).

Environment variables:
  SUPABASE_URL          — e.g. https://xxxxx.supabase.co
  SUPABASE_SERVICE_KEY  — service_role key (bypasses RLS)
"""

import json
import os
import re
from typing import Optional, Dict, Any, List

import httpx

# --- Supabase config (read lazily so env can be set before init) ---

_supabase_url: str = ""
_supabase_key: str = ""
_client: Optional[httpx.AsyncClient] = None


def _headers() -> Dict[str, str]:
    return {
        "apikey": _supabase_key,
        "Authorization": f"Bearer {_supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_url(table: str) -> str:
    return f"{_supabase_url}/rest/v1/{table}"


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(headers=_headers(), timeout=15)
    return _client


# --- Public API ---


async def init_db():
    """Initialize the httpx client. Call once at server startup."""
    global _supabase_url, _supabase_key
    _supabase_url = os.getenv("SUPABASE_URL", "")
    _supabase_key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not _supabase_url or not _supabase_key:
        import sys; print("[recipe_db] WARNING: SUPABASE_URL or SUPABASE_SERVICE_KEY not set. Recipe DB disabled.", file=sys.stderr)
        return
    await _get_client()
    import sys; print(f"[recipe_db] Connected to Supabase: {_supabase_url}", file=sys.stderr)


async def close_db():
    """Close the httpx client."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


def _extract_domain(url: str) -> str:
    """Extract domain + path from URL for matching."""
    clean = re.sub(r"https?://", "", url).replace("www.", "")
    return clean.rstrip("/")


async def match_recipe(url: str) -> Optional[Dict[str, Any]]:
    """Find a recipe matching the given URL.

    Fetches all recipes and does pattern matching in Python
    (PostgREST doesn't support reverse LIKE easily).
    """
    client = await _get_client()
    url_clean = _extract_domain(url)

    resp = await client.get(
        _rest_url("recipes"),
        params={"select": "*", "order": "times_used.desc"},
    )
    if resp.status_code != 200:
        return None

    recipes = resp.json()
    best = None
    for r in recipes:
        pattern = r.get("site_pattern", "")
        if pattern in url_clean or url_clean in pattern:
            if best is None or (r.get("times_used", 0) > best.get("times_used", 0)):
                best = r
    if best is None:
        return None

    # Deserialize config jsonb fields
    if isinstance(best.get("config"), str):
        try:
            best["config"] = json.loads(best["config"])
        except (json.JSONDecodeError, TypeError):
            pass

    return best


async def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a recipe. Upserts on site_pattern."""
    client = await _get_client()
    pattern = data["site_pattern"]

    # Check if exists
    resp = await client.get(
        _rest_url("recipes"),
        params={"site_pattern": f"eq.{pattern}", "select": "id,version"},
    )
    existing = resp.json() if resp.status_code == 200 else []

    # Build config jsonb from extra fields
    config = {}
    for key in ("wait_for", "needs_proxy", "geo_target", "api_endpoints", "pagination"):
        if data.get(key) is not None:
            config[key] = data[key]

    row = {
        "site_pattern": pattern,
        "site_name": data.get("site_name", pattern),
        "scrape_level": data.get("scrape_level", 2),
        "prompt": data.get("prompt"),
        "script": data.get("script"),
        "schema": data.get("schema"),
        "config": config if config else {},
    }

    if existing:
        # UPDATE — history trigger fires automatically
        recipe_id = existing[0]["id"]
        resp = await client.patch(
            _rest_url("recipes"),
            params={"id": f"eq.{recipe_id}"},
            json=row,
        )
        if resp.status_code not in (200, 204):
            return {"error": f"Update failed: {resp.text}"}
        updated = resp.json()
        return {
            "id": recipe_id,
            "created": False,
            "updated": True,
            "version": updated[0]["version"] if updated else existing[0].get("version", 1),
        }
    else:
        # INSERT
        resp = await client.post(
            _rest_url("recipes"),
            json=row,
        )
        if resp.status_code not in (200, 201):
            return {"error": f"Insert failed: {resp.text}"}
        created = resp.json()
        return {
            "id": created[0]["id"],
            "created": True,
            "updated": False,
            "version": 1,
        }


async def list_recipes() -> List[Dict[str, Any]]:
    """List all recipes ordered by usage."""
    client = await _get_client()
    resp = await client.get(
        _rest_url("recipes"),
        params={"select": "*", "order": "times_used.desc"},
    )
    if resp.status_code != 200:
        return []
    recipes = resp.json()
    # Add convenience flags
    for r in recipes:
        r["has_prompt"] = bool(r.get("prompt"))
        r["has_script"] = bool(r.get("script"))
        r["has_schema"] = bool(r.get("schema"))
    return recipes


async def get_recipe(recipe_id: int) -> Optional[Dict[str, Any]]:
    """Get a single recipe by ID."""
    client = await _get_client()
    resp = await client.get(
        _rest_url("recipes"),
        params={"id": f"eq.{recipe_id}", "select": "*"},
    )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0] if rows else None


async def delete_recipe(recipe_id: int) -> bool:
    """Delete a recipe by ID."""
    client = await _get_client()
    resp = await client.delete(
        _rest_url("recipes"),
        params={"id": f"eq.{recipe_id}"},
    )
    return resp.status_code in (200, 204)


async def increment_usage(recipe_id: int):
    """Increment times_used for a recipe."""
    client = await _get_client()
    # Read current value, then update (PostgREST doesn't support atomic increment easily)
    recipe = await get_recipe(recipe_id)
    if recipe:
        new_count = recipe.get("times_used", 0) + 1
        await client.patch(
            _rest_url("recipes"),
            params={"id": f"eq.{recipe_id}"},
            json={"times_used": new_count},
            headers={**_headers(), "Prefer": "return=minimal"},
        )


async def get_recipe_history(recipe_id: int) -> List[Dict[str, Any]]:
    """Get version history for a recipe."""
    client = await _get_client()
    resp = await client.get(
        _rest_url("recipe_history"),
        params={
            "recipe_id": f"eq.{recipe_id}",
            "select": "*",
            "order": "version.desc",
        },
    )
    if resp.status_code != 200:
        return []
    return resp.json()
