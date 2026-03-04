"""Recipe database — async SQLite for scraping recipes."""

import re
import aiosqlite
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

DB_PATH = Path.home() / ".scrapelab" / "recipes.db"

_db: Optional[aiosqlite.Connection] = None

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS recipes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_pattern TEXT UNIQUE NOT NULL,
    site_name TEXT NOT NULL,
    prompt TEXT,
    scrape_level INTEGER DEFAULT 2,
    wait_for TEXT,
    needs_proxy INTEGER DEFAULT 0,
    geo_target TEXT,
    api_endpoints TEXT,
    pagination TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    times_used INTEGER DEFAULT 0,
    success_rate REAL DEFAULT 0.0
);
"""


async def init_db():
    """Initialize the recipe database. Call once at server startup."""
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute(CREATE_TABLE)
    await _db.commit()


async def close_db():
    """Close the database connection. Call at server shutdown."""
    global _db
    if _db:
        await _db.close()
        _db = None


def _extract_domain(url: str) -> str:
    """Extract domain from URL, stripping protocol and www."""
    return re.sub(r"https?://", "", url).split("/")[0].replace("www.", "")


async def match_recipe(url: str) -> Optional[Dict[str, Any]]:
    """Find a recipe matching the given URL's domain."""
    if not _db:
        return None
    domain = _extract_domain(url)
    cursor = await _db.execute(
        "SELECT * FROM recipes WHERE ? LIKE '%' || site_pattern || '%' "
        "OR site_pattern LIKE ? ORDER BY times_used DESC LIMIT 1",
        (domain, f"%{domain}%"),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    return dict(row)


async def save_recipe(data: Dict[str, Any]) -> Dict[str, Any]:
    """Save or update a recipe. Upserts on site_pattern."""
    if not _db:
        raise RuntimeError("Recipe DB not initialized")

    existing = await _db.execute(
        "SELECT id FROM recipes WHERE site_pattern = ?", (data["site_pattern"],)
    )
    row = await existing.fetchone()

    if row:
        await _db.execute(
            """UPDATE recipes SET site_name=?, prompt=?, scrape_level=?, wait_for=?,
               needs_proxy=?, geo_target=?, api_endpoints=?, pagination=?,
               updated_at=? WHERE id=?""",
            (
                data.get("site_name"),
                data.get("prompt"),
                data.get("scrape_level", 2),
                data.get("wait_for"),
                data.get("needs_proxy", 0),
                data.get("geo_target"),
                data.get("api_endpoints"),
                data.get("pagination"),
                datetime.utcnow().isoformat(),
                row["id"],
            ),
        )
        await _db.commit()
        return {"id": row["id"], "updated": True}
    else:
        cursor = await _db.execute(
            """INSERT INTO recipes (site_pattern, site_name, prompt, scrape_level,
               wait_for, needs_proxy, geo_target, api_endpoints, pagination)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["site_pattern"],
                data["site_name"],
                data.get("prompt"),
                data.get("scrape_level", 2),
                data.get("wait_for"),
                data.get("needs_proxy", 0),
                data.get("geo_target"),
                data.get("api_endpoints"),
                data.get("pagination"),
            ),
        )
        await _db.commit()
        return {"id": cursor.lastrowid, "created": True}


async def list_recipes() -> List[Dict[str, Any]]:
    """List all recipes ordered by usage."""
    if not _db:
        return []
    cursor = await _db.execute(
        "SELECT id, site_pattern, site_name, scrape_level, times_used, "
        "success_rate, created_at FROM recipes ORDER BY times_used DESC"
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_recipe(recipe_id: int) -> bool:
    """Delete a recipe by ID."""
    if not _db:
        return False
    cursor = await _db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    await _db.commit()
    return cursor.rowcount > 0


async def increment_usage(recipe_id: int):
    """Increment times_used for a recipe."""
    if not _db:
        return
    await _db.execute(
        "UPDATE recipes SET times_used = times_used + 1 WHERE id = ?", (recipe_id,)
    )
    await _db.commit()
