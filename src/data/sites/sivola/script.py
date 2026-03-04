"""Sivola itinerary page scraper.

Extracts tour info + all departures from a Sivola itinerary page.
Works with httpx (no browser needed) — pages are SSR.

Usage:
    python script.py https://www.sivola.it/viaggi/thailandia-summer-zaino-in-spalla
"""

import httpx
import re
import json
import sys
from datetime import datetime

MONTHS_IT = {
    "gen": 1, "feb": 2, "mar": 3, "apr": 4, "mag": 5, "giu": 6,
    "lug": 7, "ago": 8, "set": 9, "ott": 10, "nov": 11, "dic": 12,
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def parse_departures(html: str, url: str) -> dict:
    """Parse a Sivola itinerary page and extract tour info + departures."""

    # --- Tour info ---
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
    tour_name = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', title_match.group(1))).strip() if title_match else ""

    duration_match = re.search(r'(\d+)\s*giorni', html)
    duration_days = int(duration_match.group(1)) if duration_match else None

    slug = url.rstrip("/").split("/")[-1]

    # Age range
    age_match = re.search(r'Viaggio aperto per\s*</?\w[^>]*>\s*(\d+-\d+|Libero)', html)
    age_range = age_match.group(1) if age_match else None

    # --- Departures from the list section ---
    departures = []

    # Split HTML by "Prenota ora" to get individual departure blocks (preserving HTML for coordinator links)
    html_blocks = re.split(r'Prenota ora', html)

    for html_block in html_blocks:
        # Strip tags for text parsing
        block = re.sub(r'<[^>]+>', ' ', html_block)
        block = re.sub(r'\s+', ' ', block)

        # Find date pattern: DD mmm Ngg
        date_m = re.search(
            r'(\d{1,2})\s+(gen|feb|mar|apr|mag|giu|lug|ago|set|ott|nov|dic)\s+(\d+)gg',
            block,
        )
        if not date_m:
            continue

        day = int(date_m.group(1))
        month_str = date_m.group(2)
        month = MONTHS_IT.get(month_str)
        dur = int(date_m.group(3))

        if not month:
            continue

        # Determine year from context (current year or next)
        now = datetime.now()
        year = now.year
        if month < now.month or (month == now.month and day < now.day):
            year += 1

        # City — appears after the duration
        after_date = block[date_m.end():]
        city_m = re.search(
            r'(Milano|Roma|Venezia|Napoli|Torino|Bologna|Firenze|Palermo|Catania|Bari)',
            after_date,
        )
        city = city_m.group(1) if city_m else None

        # Coordinator — search in original HTML block (has <a href="/coordinatori/...">)
        coord_m = re.search(r'/coordinatori/([\w-]+)', html_block)
        coordinator = coord_m.group(1) if coord_m else None

        # Price — Totale
        price_m = re.search(r'Totale\s+(\d+)\s*€', after_date)
        price = int(price_m.group(1)) if price_m else None

        # Deposit — Acconto
        deposit_m = re.search(r'Acconto\s+(\d+)\s*€', after_date)
        deposit = int(deposit_m.group(1)) if deposit_m else None

        # Status
        status = "available"
        spots_left = None
        spots_n = re.search(r'Ultimi\s+(\d+)\s+posti', block, re.IGNORECASE)
        if spots_n:
            status = "last_spots"
            spots_left = int(spots_n.group(1))
        elif re.search(r'Ultimi\s+posti', block, re.IGNORECASE):
            status = "last_spots"
        elif re.search(r'Sold\s*out', block, re.IGNORECASE):
            status = "sold_out"

        dep = {
            "departureDate": f"{year}-{month:02d}-{day:02d}",
            "durationDays": dur,
            "departureCity": city,
            "coordinator": coordinator,
            "price": price,
            "deposit": deposit,
            "status": status,
        }
        if spots_left is not None:
            dep["spotsLeft"] = spots_left

        departures.append(dep)

    return {
        "url": url,
        "slug": slug,
        "tourName": tour_name,
        "durationDays": duration_days,
        "ageRange": age_range,
        "totalDepartures": len(departures),
        "departures": departures,
    }


async def scrape(url: str) -> dict:
    """Fetch and parse a Sivola itinerary page."""
    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=30
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    return parse_departures(resp.text, url)


if __name__ == "__main__":
    import asyncio

    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://www.sivola.it/viaggi/thailandia-summer-zaino-in-spalla"
    )
    result = asyncio.run(scrape(url))
    print(json.dumps(result, indent=2, ensure_ascii=False))
