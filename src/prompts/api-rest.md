# REST API Scraping — Knowledge Base

> Referenced from [agent.md](./agent.md) when a site has REST API endpoints.

---

## When to Use

- Site has `/api/`, `/wp-json/`, `/data/`, or similar endpoints
- Network tab shows JSON responses when browsing
- URL patterns like `?page=1&limit=50` or `/items?offset=0`

---

## Discovery Techniques

### 1. Network Tab Inspection
Open DevTools → Network → filter "XHR/Fetch" → navigate the site → look for JSON responses containing the data you need.

### 2. Common API Patterns
```
/api/v1/products
/api/v2/departures?trip_id=X
/wp-json/wp/v2/posts?per_page=100
/trips/json/departures/?trip_id=X
```

### 3. Hidden API Hints in HTML
```bash
# Search page source for API clues
curl -s "URL" | grep -oE '"(https?://[^"]*api[^"]*)"' | sort -u
curl -s "URL" | grep -oE '/api/[^"'\'']*' | sort -u
```

---

## Pagination Patterns

### Offset-based
```javascript
let page = 1;
let hasMore = true;
while (hasMore) {
    const { body } = await gotScraping({
        url: `${BASE}/api/items?page=${page}&per_page=100`,
        responseType: 'json',
    });
    results.push(...body.data);
    hasMore = page < body.lastPage; // or body.total > results.length
    page++;
}
```

### Cursor-based
```javascript
let cursor = null;
do {
    const url = cursor
        ? `${BASE}/api/items?cursor=${cursor}`
        : `${BASE}/api/items`;
    const { body } = await gotScraping({ url, responseType: 'json' });
    results.push(...body.items);
    cursor = body.nextCursor;
} while (cursor);
```

---

## Authentication & Headers

Some APIs require specific headers:
```javascript
const { body } = await gotScraping({
    url: endpoint,
    headers: {
        'Accept': 'application/json',
        'Accept-Language': 'en-EU',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://site.com/tours',
    },
    responseType: 'json',
});
```

---

## Rate Limiting

API scrapers can run much higher concurrency than DOM scrapers:
- **No rate limit detected:** 10-20 concurrent requests
- **429 responses:** Back off, reduce to 3-5 concurrent, add delays
- **Always respect `Retry-After` headers**

```javascript
// Simple rate limiter
const delay = (ms) => new Promise(r => setTimeout(r, ms));
for (const url of urls) {
    results.push(await fetchData(url));
    await delay(200); // 200ms between requests
}
```

---

## Common Gotchas

### Filter parameters that don't work
**Problem:** `?category=europe` doesn't actually filter — returns same total.
**Fix:** Always verify filters by comparing filtered vs unfiltered totals. Some APIs need:
- Array notation: `?categoryId[]=uuid`
- POST body instead of query params
- Specific headers (`Content-Type: application/json`)

### Paginated responses with changing data
**Problem:** Items shift between pages during scraping (new items added/removed).
**Fix:** Deduplicate by unique ID at the end.

### API versioning
**Problem:** `/api/v1/` stops working, switched to `/api/v2/`.
**Fix:** During recon, check for version hints in page source or network requests.

---

## Real-World Examples

### Intrepid Travel (REST + Sitemap)
- Discovery: sitemap → product URLs → extract product code from meta tag
- API: `/api/product/available-years-months-and-departures?product_code=X&product_id=Y&currency_code=eur`
- Paginated: `numberOfPages` field in response
- Concurrency: 10 (no rate limiting detected)

### G Adventures (Hybrid: REST + DOM)
- Discovery: sitemap → trip URLs → extract trip ID via 6 regex patterns
- API: `/trips/json/departures/?trip_id=X&show_waitlist=true`
- Groups departures by `compass_id`, averages prices across room types
- Needs residential proxy (geo-blocking)

### Les Aventureurs (Remix turbo-stream API)
- Discovery: catalogue pagination at `/catalogue.data?page=N&_routes=routes%2Fcatalogue`
- Decoded via `turbo-stream` npm package → `catalogPromise.searchProgrammes.edges[].node.slug`
- 9 items per page, `totalCount` field for calculating total pages
- Departures: `/offre/{slug}/departs.data?_routes=...` → `programmeDepartureListPromise.programme.departures.edges[].node`
- Prices in cents (divide by 100), ISO dates with timezone offsets (extract via regex, NOT `new Date()`)
- Sequential processing (1 URL at a time, 500ms delay) — lightweight API, no rate limiting issues
- See also: [frameworks.md](./frameworks.md) Remix section for turbo-stream decoding details

---

## Common Gotcha: Timezone-Shifted Dates

When APIs return ISO dates with timezone offsets (e.g. `"2026-06-20T00:00:00+02:00"`), **never use `new Date()` for date extraction** on cloud servers (Apify, AWS, etc.) which run in UTC.

`new Date("2026-06-20T00:00:00+02:00").getDate()` → **19** (not 20!)

Always extract date components via string parsing:
```javascript
const match = isoStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
const year = match[1], month = match[2], day = match[3];
```

This applies to any API returning timezone-aware dates (Remix, Rails, Django, etc.).

---

*Last updated: 2026-02-21*
