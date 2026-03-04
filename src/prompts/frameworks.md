# SPA Framework Scraping — Knowledge Base

> Referenced from [agent.md](./agent.md) for sites built with modern JavaScript frameworks.

---

## Framework Detection

```bash
# Quick framework detection
curl -s "URL" | grep -iE "__NEXT_DATA__|__NUXT__|_gatsby|__REMIX|angular|ember" | head -3
```

| Clue in HTML | Framework | Data strategy |
|-------------|-----------|--------------|
| `<script id="__NEXT_DATA__">` | Next.js | Parse embedded JSON |
| `window.__NUXT__` | Nuxt.js (Vue) | Evaluate in browser context |
| `_gatsby` | Gatsby | Static JSON in page data |
| `window.__remixContext` | Remix | Turbo-stream or loader data |
| `<div id="app">` + empty body | Vue/React SPA | Need browser rendering |

---

## Next.js

### Data extraction (no browser needed!)
Next.js embeds page data in a `<script id="__NEXT_DATA__">` tag:

```javascript
import { gotScraping } from 'got-scraping';
import * as cheerio from 'cheerio';

async function getNextData(url) {
    const { body } = await gotScraping({ url });
    const $ = cheerio.load(body);
    const nextDataScript = $('#__NEXT_DATA__').html();
    if (!nextDataScript) return null;

    const data = JSON.parse(nextDataScript);
    return data.props?.pageProps;
}
```

### API routes
Next.js apps often have API routes at `/api/...`:
```bash
# Look for API routes in page source
curl -s "URL" | grep -oE '"/api/[^"]*"' | sort -u
```

### Data fetching pattern
Next.js pages can also fetch data client-side. Check the Network tab for:
- `/_next/data/{buildId}/{page}.json` — server-side props as JSON
- `/api/...` — custom API routes

---

## Nuxt.js

### Data extraction
Nuxt embeds data in `window.__NUXT__`, but it's often a minified IIFE, not raw JSON. Must evaluate in browser:

```javascript
// Use Playwright to extract Nuxt data
const nuxtData = await page.evaluate(() => {
    const nuxt = window.__NUXT__;
    if (!nuxt) return null;
    return {
        data: nuxt.data,
        state: nuxt.state,
        // Look for API URLs in the data
    };
});
```

### Nuxt API routes
Nuxt apps often have `/api/` routes or use `useFetch` with specific endpoints visible in the Network tab.

### AsyncData / Fetch
Data loaded via `asyncData` or `fetch` hooks is in `window.__NUXT__.data[0]`. Drill into this to find the actual items.

---

## Remix

### Turbo-Stream responses
Remix v2+ uses Turbo-Stream format for data loading. Endpoints use `.data` suffix:

```bash
# Turbo-stream data endpoints (note .data suffix, not ?_data=)
curl -s "https://site.com/catalogue.data" -H "Accept: text/x-script"
curl -s "https://site.com/offre/my-tour/departs.data" -H "Accept: text/x-script"
```

### Route filtering with `_routes` parameter
Remix single-fetch supports `_routes` param to request specific route data:
```bash
# Only fetch data for the catalogue route
curl -s "https://site.com/catalogue.data?page=1&_routes=routes%2Fcatalogue"
# Multiple routes (URL-encoded comma)
curl -s "https://site.com/offre/slug/departs.data?_routes=routes%2Foffre.%24slug%2Croutes%2Foffre.%24slug.departs"
```

### Decoding turbo-stream with the `turbo-stream` npm package
The turbo-stream wire format is complex (references, template objects, deferred promises). **Do NOT try to parse it manually** — use the official `turbo-stream` npm package:

```javascript
import { decode } from 'turbo-stream';

async function decodeTurboStream(responseBody) {
    const stream = new ReadableStream({
        start(controller) {
            controller.enqueue(new TextEncoder().encode(responseBody));
            controller.close();
        }
    });
    const result = await decode(stream);
    return result.value; // Clean JS object with route data
}

// Example: decoded['routes/catalogue']?.data?.catalogPromise
// Promises in the decoded object must be awaited
const catalog = await routeData.catalogPromise;
```

### ⚠️ Timezone pitfall with ISO dates from Remix APIs
Remix APIs often return ISO dates with timezone offsets (e.g. `"2026-06-20T00:00:00+02:00"`). **NEVER use `new Date()` to extract day/month** — on UTC servers (like Apify), `new Date("2026-06-20T00:00:00+02:00").getDate()` returns **19** (converted to UTC = 22:00 on June 19th).

**Fix:** Extract date components directly via regex:
```javascript
function parseLocalDate(isoStr) {
    const match = isoStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return null;
    return { year: parseInt(match[1]), month: parseInt(match[2]) - 1, day: parseInt(match[3]) };
}
```

### Legacy loader data (Remix v1)
Older Remix sites may use `?_data=` pattern instead of `.data` suffix:
```bash
# Pattern: {url}?_data=routes/{route-id}
curl -s "https://site.com/tours?_data=routes/tours"
```

### Real-world examples

**Les Aventureurs (turbo-stream API — full API scraper, no browser):**
- Discovery: catalogue pagination at `/catalogue.data?page=N` → `catalogPromise.searchProgrammes.edges[].node.slug`
- Departures: `/offre/{slug}/departs.data` → `programmeDepartureListPromise.programme.departures.edges[].node`
- Fields available: `travelStart`, `travelEnd`, `complete` (sold out), `remainingPlaceCount`, `currentPricing.total.amount` (cents), `regularPricing.total.amount`, `expired`
- Uses `turbo-stream` npm package for decoding — works perfectly, no browser needed
- Package: `"turbo-stream": "^2.0.0"` in dependencies

**Copines de Voyage (Remix — switched to DOM):**
- Initially used turbo-stream API for catalogue discovery, fetching slugs via `/catalogue.data?page=N`. But departure detail extraction was fragile and eventually replaced with DOM scraping.
- **Lesson learned:** If the turbo-stream decode works cleanly (like Les Aventureurs), prefer API. If the data structure is too nested or changes frequently, fall back to DOM.

---

## Gatsby

### Static data
Gatsby pre-renders all data at build time. Look for:
```bash
# Page data files
curl -s "https://site.com/page-data/index/page-data.json"
curl -s "https://site.com/page-data/{path}/page-data.json"
```

### GraphQL at build time
Gatsby uses GraphQL internally but doesn't expose it at runtime. All data is pre-baked into static files.

---

## Generic SPA (Vue/React without SSR)

When the HTML is essentially empty (`<div id="app"></div>`) and all content is client-rendered:

1. **Must use Playwright** — no shortcuts
2. **Look for API calls** in Network tab — the SPA is fetching data from somewhere
3. **Network interception** is often the best approach:

```javascript
import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage();

const apiResponses = [];
page.on('response', async (response) => {
    const contentType = response.headers()['content-type'] || '';
    if (contentType.includes('application/json')) {
        try {
            const body = await response.json();
            apiResponses.push({ url: response.url(), body });
        } catch {}
    }
});

await page.goto(url, { waitUntil: 'networkidle' });
// Now inspect apiResponses to find the data
```

---

## Framework-Specific Gotchas

### Hydration mismatch
SSR frameworks render HTML on the server, then "hydrate" it client-side. The initial HTML may have placeholder data that gets replaced. Always wait for hydration to complete:
```javascript
await page.waitForFunction(() => {
    // Check that Vue/React has hydrated
    return document.querySelector('[data-v-]') || document.querySelector('[data-reactroot]');
});
```

### Route changes without page reload
SPAs use client-side routing — clicking a link doesn't trigger a full page load:
```javascript
// Must use page.click() + waitForNavigation, not page.goto()
await Promise.all([
    page.waitForNavigation({ waitUntil: 'networkidle' }),
    page.click('a[href="/tours/details"]'),
]);
```

### Build ID changes
Next.js `/_next/data/{buildId}/...` URLs change on every deployment. Don't hardcode the buildId — extract it from `__NEXT_DATA__` first.

---

*Last updated: 2026-02-21*
