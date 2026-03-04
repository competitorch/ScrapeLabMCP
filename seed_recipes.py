"""Seed existing site bundles (Sivola + WeRoad) into Supabase.

Run once after creating the tables:
    python seed_recipes.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from recipe_db import init_db, close_db, save_recipe

# --- Supabase credentials (fallback to hardcoded for seeding) ---
os.environ.setdefault("SUPABASE_URL", "https://txsvivigodnlicbehqej.supabase.co")
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR4c3Zpdmlnb2RubGljYmVocWVqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MjY0MTgwNiwiZXhwIjoyMDg4MjE3ODA2fQ.XigHEmGNJKbI1S4s-Ar38VSiwTL2ifwkLIbV6HOns4o",
)

SITES_DIR = Path(__file__).parent / "src" / "data" / "sites"


def load_site_bundle(slug: str) -> dict:
    """Load a site bundle from disk into a recipe dict."""
    d = SITES_DIR / slug
    config = json.loads((d / "config.json").read_text())

    prompt = ""
    if (d / "prompt.md").exists():
        prompt = (d / "prompt.md").read_text()

    script = ""
    if (d / "script.py").exists():
        script = (d / "script.py").read_text()

    schema = None
    if (d / "schema.json").exists():
        schema = json.loads((d / "schema.json").read_text())

    return {
        "site_pattern": config["site_pattern"],
        "site_name": config["site_name"],
        "scrape_level": config.get("scrape_level", 2),
        "prompt": prompt or None,
        "script": script or None,
        "schema": schema,
        "wait_for": config.get("wait_for"),
        "needs_proxy": config.get("needs_proxy", False),
        "geo_target": config.get("geo_target"),
        "api_endpoints": config.get("api_endpoints"),
        "pagination": config.get("pagination"),
    }


async def main():
    await init_db()

    slugs = [d.name for d in sorted(SITES_DIR.iterdir()) if d.is_dir() and (d / "config.json").exists()]
    print(f"Found {len(slugs)} site bundles: {slugs}")

    for slug in slugs:
        data = load_site_bundle(slug)
        result = await save_recipe(data)
        status = "CREATED" if result.get("created") else "UPDATED"
        print(f"  {status}: {data['site_name']} (id={result.get('id')})")

    await close_db()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
