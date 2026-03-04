"""WeRoad IT departures scraper.

Extracts all departures for a given travel via the public catalog API.
Works with httpx (no browser needed) — pure REST API.

Usage:
    python script.py https://www.weroad.it/viaggi/tour-thailandia-chiang-mai-koh-tao
    python script.py tour-thailandia-chiang-mai-koh-tao
"""

import httpx
import json
import sys
import asyncio

API_BASE = "https://api-catalog.weroad.it/travels"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
}


def extract_slug(url_or_slug: str) -> str:
    """Extract travel slug from URL or return as-is if already a slug."""
    if "/" in url_or_slug:
        # URL like https://www.weroad.it/viaggi/tour-thailandia-chiang-mai-koh-tao?status[]=...
        path = url_or_slug.split("?")[0].rstrip("/")
        return path.split("/")[-1]
    return url_or_slug


def parse_departure(t: dict) -> dict:
    """Parse a single departure from the API response."""
    dep = {
        "id": t["id"],
        "startingDate": t["startingDate"],
        "endingDate": t["endingDate"],
        "priceEUR": t["price"]["EUR"],
        "priceCHF": t["price"].get("CHF"),
        "depositEUR": t.get("depositPrice", {}).get("EUR"),
        "salesStatus": t["salesStatus"],
        "ageBadge": t.get("ageBadge"),
        "coordinator": None,
        "interestedCount": t.get("groupInfo", {}).get("interestedCount"),
        "expectedGroupSize": t.get("groupInfo", {}).get("expectedGroupSizeCount"),
        "seatsToConfirm": t.get("seatsToConfirm"),
        "freeSeats": t.get("freeSeats"),
    }

    coord = t.get("coordinator")
    if coord:
        dep["coordinator"] = f"{coord['firstName']} {coord['lastName']}"

    return dep


async def scrape(url_or_slug: str) -> dict:
    """Fetch all departures for a WeRoad travel."""
    slug = extract_slug(url_or_slug)
    api_url = f"{API_BASE}/{slug}/tours/paginated?show=true"

    async with httpx.AsyncClient(
        headers=HEADERS, follow_redirects=True, timeout=30
    ) as client:
        # First page to get pagination info
        resp = await client.get(f"{api_url}&page=1")
        resp.raise_for_status()
        data = resp.json()["data"]

        last_page = data["lastPage"]
        total = data["total"]
        travel_info = data["data"][0]["travel"] if data["data"] else {}

        departures = [parse_departure(t) for t in data["data"]]

        # Fetch remaining pages
        for page in range(2, last_page + 1):
            resp = await client.get(f"{api_url}&page={page}")
            resp.raise_for_status()
            page_data = resp.json()["data"]["data"]
            departures.extend(parse_departure(t) for t in page_data)

    return {
        "url": f"https://www.weroad.it/viaggi/{slug}",
        "slug": slug,
        "travelTitle": travel_info.get("title", ""),
        "numberOfDays": travel_info.get("numberOfDays"),
        "totalDepartures": len(departures),
        "departures": departures,
    }


if __name__ == "__main__":
    url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://www.weroad.it/viaggi/tour-thailandia-chiang-mai-koh-tao"
    )
    result = asyncio.run(scrape(url))
    print(json.dumps(result, indent=2, ensure_ascii=False))
