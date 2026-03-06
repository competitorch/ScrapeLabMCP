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

### Known slugs (Thailandia)
| Travel Name | Slug |
|---|---|
| Thailandia 360° Summer: Bangkok, il nord e Koh Tao | `tour-thailandia-chiang-mai-koh-tao` |
| Thailandia 360° Winter: Bangkok, Chiang Mai e Phi Phi Island | `tour-thailandia-bangkok-chiang-mai-phuket-krabi` |

## Extraction

### API Response Structure
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
        "basePrice": null,
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
        "bookingPillars": {
          "freeCancellation": true,
          "bookWithDeposit": true,
          "interestFreeInstallments": true
        },
        "travel": {
          "title": "...",
          "slug": "...",
          "numberOfDays": 12,
          "travelStyle": { "displayName": "Classic" },
          "travelTypes": [{ "code": "TS", "displayName": "360°" }]
        }
      }
    ]
  }
}
```

### Fields to extract per departure
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
| coordinator | `coordinator.firstName + coordinator.lastName` | null if not assigned |
| interestedCount | `groupInfo.interestedCount` | null for confirmed tours |
| expectedGroupSize | `groupInfo.expectedGroupSizeCount` | Target group size |
| seatsToConfirm | `seatsToConfirm` | Seats needed to confirm, null if already confirmed |
| freeSeats | `freeSeats` | Available seats |
| noSharingRoom | `isNoSharingRoomAvailable` | Private room option |
| discountPct | `discountPercentage` | null if no discount |
| travelTitle | `travel.title` | Full travel name |
| numberOfDays | `travel.numberOfDays` | Trip duration |
| travelStyle | `travel.travelStyle.displayName` | Classic, etc. |

## Pagination Loop (JavaScript/Node)
```javascript
async function scrapeWeRoadDepartures(slug) {
  const baseUrl = `https://api-catalog.weroad.it/travels/${slug}/tours/paginated?show=true`;
  const allDepartures = [];
  
  // Get first page to know total pages
  const firstResp = await fetch(`${baseUrl}&page=1`);
  const firstJson = await firstResp.json();
  const lastPage = firstJson.data.lastPage;
  
  // Extract from first page
  firstJson.data.data.forEach(t => allDepartures.push(extractFields(t)));
  
  // Fetch remaining pages
  for (let page = 2; page <= lastPage; page++) {
    const resp = await fetch(`${baseUrl}&page=${page}`);
    const json = await resp.json();
    json.data.data.forEach(t => allDepartures.push(extractFields(t)));
    await sleep(500); // Be respectful
  }
  
  return { total: allDepartures.length, departures: allDepartures };
}

function extractFields(t) {
  return {
    id: t.id,
    startingDate: t.startingDate,
    endingDate: t.endingDate,
    priceEUR: t.price.EUR,
    priceCHF: t.price.CHF,
    salesStatus: t.salesStatus,
    ageBadge: t.ageBadge,
    coordinator: t.coordinator ? `${t.coordinator.firstName} ${t.coordinator.lastName}` : null,
    interestedCount: t.groupInfo.interestedCount,
    expectedGroupSize: t.groupInfo.expectedGroupSizeCount,
    seatsToConfirm: t.seatsToConfirm,
    freeSeats: t.freeSeats,
    travelTitle: t.travel.title,
    numberOfDays: t.travel.numberOfDays
  };
}
```

## Notes
- The API is completely public, no auth tokens or cookies needed
- `show=true` parameter filters for visible/active departures only
- The `status[]` query params on the website URLs are frontend filters only — the API returns all statuses
- Prices vary by season: summer peak (Jul-Aug) tends to be €1499, shoulder months €1449
- Two departures can share the same startingDate (different ageBadge groups)
- Coordinator is assigned only after a tour is CONFIRMED
- `interestedCount` becomes null once a tour reaches CONFIRMED status

## Validated: 2026-03-04
- 76 departures extracted for slug `tour-thailandia-chiang-mai-koh-tao`
- All fields match website display
