# WeRoad IT — Travel Departures Scraper

## Overview
- **Site**: weroad.it (Italian travel company, group adventures)
- **Framework**: Nuxt.js (Vue SSR)
- **Strategy**: Pure API (Level 1 — HTTP only, no browser needed)
- **Auth**: None required
- **Rate limiting**: Not observed, but be respectful (1-2 req/s recommended)

## Architecture Discovery

### Catalog API
WeRoad exposes a public REST API for departure data:

```
GET https://api-catalog.weroad.it/travels/{travel-slug}/tours/paginated?show=true&page={n}
```

- **No authentication** required
- **CORS enabled** (can be called from browser or server)
- **Pagination**: 20 items per page, `data.lastPage` tells total pages
- **Response format**: JSON with nested structure

### How to find the travel slug
1. Navigate to `https://www.weroad.it/destinazioni/asia/thailandia` (or any destination page)
2. Travel cards contain `<a>` tags with `data-testid="travel-card-title"` and `href="/viaggi/{slug}?status[]=..."`
3. The slug is the path segment after `/viaggi/` before the `?`

## API Response Structure
```json
{
  "response": "success",
  "data": {
    "currentPage": 1,
    "lastPage": 4,
    "total": 76,
    "perPage": 20,
    "data": [
      {
        "id": "uuid",
        "startingDate": "2026-05-01",
        "endingDate": "2026-05-12",
        "price": { "EUR": 1499, "CHF": 1358 },
        "depositPrice": { "EUR": 100, "CHF": 90 },
        "salesStatus": "CONFIRMED|ALMOST_CONFIRMED|PLANNED|ALMOST_FULL|WAITING_LIST",
        "ageBadge": "25-35|35-49",
        "coordinator": {
          "firstName": "...",
          "lastName": "...",
          "nickname": "...",
          "city": "..."
        },
        "groupInfo": {
          "hasPax": true,
          "interestedCount": 20,
          "expectedGroupSizeCount": 13
        },
        "seatsToConfirm": null,
        "freeSeats": null,
        "isNoSharingRoomAvailable": true,
        "discountPercentage": null,
        "travel": {
          "title": "...",
          "slug": "...",
          "numberOfDays": 12,
          "travelStyle": { "displayName": "Classic" },
          "travelTypes": [{ "code": "TS", "displayName": "360" }]
        }
      }
    ]
  }
}
```

## Fields to Extract

| Field | Path | Notes |
|---|---|---|
| id | `id` | UUID |
| startingDate | `startingDate` | ISO date |
| endingDate | `endingDate` | ISO date |
| priceEUR | `price.EUR` | Integer, euros |
| priceCHF | `price.CHF` | Integer, francs |
| depositEUR | `depositPrice.EUR` | Usually 100 |
| salesStatus | `salesStatus` | CONFIRMED, ALMOST_CONFIRMED, PLANNED, ALMOST_FULL, WAITING_LIST |
| ageBadge | `ageBadge` | "25-35" or "35-49" |
| coordinator | `coordinator.firstName + lastName` | null if not assigned |
| interestedCount | `groupInfo.interestedCount` | null for confirmed tours |
| expectedGroupSize | `groupInfo.expectedGroupSizeCount` | Target group size |
| seatsToConfirm | `seatsToConfirm` | Seats needed to confirm |
| freeSeats | `freeSeats` | Available seats |
| numberOfDays | `travel.numberOfDays` | Trip duration |
| travelTitle | `travel.title` | Full travel name |

## Notes
- The API is completely public, no auth tokens or cookies needed
- `show=true` parameter filters for visible/active departures only
- The `status[]` query params on the website URLs are frontend filters only — the API returns all statuses
- Prices vary by season: summer peak (Jul-Aug) tends to be higher
- Two departures can share the same startingDate (different ageBadge groups)
- Coordinator is assigned only after a tour is CONFIRMED
- `interestedCount` becomes null once a tour reaches CONFIRMED status
