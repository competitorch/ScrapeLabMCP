# ScrapeLab Knowledge Base — Agent Core

> This file is the central index of accumulated scraping knowledge.
> It references specialist files for specific site types and patterns.
> Updated after every scraping session with new insights.

---

## Strategy Priority

**Always try approaches in this order:**

```
1. API (REST/GraphQL)     ← fastest, most reliable, least detectable
2. Hybrid (API + DOM)     ← when API is incomplete (missing fields)
3. DOM (Playwright)       ← last resort, slowest, most fragile
```

API scrapers are 10x more reliable than DOM scrapers. They don't break when CSS changes, they're faster, lighter on resources, and harder to detect. **Exhaust all API options before falling back to DOM.**

---

## Specialist Files

| File | When to read |
|------|-------------|
| [api-rest.md](./api-rest.md) | Site has REST API, wp-json, or data endpoints |
| [api-graphql.md](./api-graphql.md) | Site uses GraphQL (Apollo, Relay, custom) |
| [dom-playwright.md](./dom-playwright.md) | No API found, must scrape rendered HTML |
| [ecommerce.md](./ecommerce.md) | E-commerce sites (Shopify, WooCommerce, Magento, etc.) |
| [wordpress.md](./wordpress.md) | WordPress-based sites |
| [frameworks.md](./frameworks.md) | SPA frameworks: Next.js, Nuxt.js, Remix, Gatsby |

---

## Universal Anti-Patterns (Things That Always Break)

### 1. Modulo-based state saves with variable batch sizes
**Problem:** `if ((index + 1) % 10 === 0)` never triggers when batch size doesn't divide evenly into 10.
**Example:** Batch size 3 produces indices 2, 5, 8, 11... Remainders: 3, 6, 9, 12 — never 0.
**Fix:** Use a counter that accumulates and resets:
```javascript
let itemsSinceLastSave = 0;
itemsSinceLastSave += batchSize;
if (itemsSinceLastSave >= 10 || isLastBatch) {
    await pushData(results);
    await saveState();
    itemsSinceLastSave = 0;
}
```

### 2. High concurrency on limited RAM
**Problem:** Playwright browsers consume ~200-400MB each. 10 concurrent tabs on 1GB = instant OOM.
**Fix:** Match concurrency to available memory:
| RAM | Max Playwright tabs |
|-----|-------------------|
| 1 GB | 2 |
| 2 GB | 3-4 |
| 4 GB | 5-8 |
| 8 GB | 10-15 |

API scrapers can run 10-20x higher concurrency since they don't use browsers.

### 3. `networkidle` wait strategy
**Problem:** Modern sites with analytics, websockets, and trackers never reach networkidle.
**Fix:** Use `domcontentloaded` with explicit waits:
```javascript
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForSelector('.departure-card', { timeout: 10000 });
```

### 4. CSS class selectors on modern frameworks
**Problem:** Generated classes like `.css-1abc23` or `.sc-bdVTJa` change on every build.
**Fix:** Prefer stable selectors:
- `[data-testid="..."]`
- `[itemprop="price"]`
- `button:has-text("Book")`
- Semantic HTML: `article`, `section`, `time[datetime]`

### 5. Not deduplicating responsive layouts
**Problem:** Sites render mobile + desktop versions in the same DOM (hidden via CSS).
**Fix:** Always check for `.d-none`, `.d-md-block`, `.not-mobile`, `.only-mobile`, `fresnel-*` containers. Extract only one variant.

---

## Universal Best Practices

### Reconnaissance First
Never write a scraper without understanding the site:
1. Check `/robots.txt`, `/sitemap.xml`
2. Open DevTools Network tab, navigate, watch for JSON responses
3. Look for `__NEXT_DATA__`, `__NUXT__`, `window.__INITIAL_STATE__`
4. Check for API endpoints in page source

### State Management Pattern
Save progress every N URLs so crashes don't lose all work:
```javascript
// Counter-based (proven reliable across all batch sizes)
let urlsSinceLastSave = 0;
urlsSinceLastSave += processedCount;
if (urlsSinceLastSave >= SAVE_INTERVAL || isLastBatch) {
    await dataset.pushData(buffer);
    buffer = [];
    await stateManager.save();
    urlsSinceLastSave = 0;
}
```

### Price Normalisation
Always store prices as integer strings, no decimals, no symbols:
```javascript
function cleanPrice(raw) {
    if (!raw) return '';
    return String(Math.round(
        parseFloat(raw.replace(/[€$£\s]/g, '').replace(/\./g, '').replace(',', '.'))
    ));
}
```
European format `1.397,50` → remove dots → `1397,50` → comma to dot → `1397.50` → round → `"1398"`

### Profile Fallback for DOM scrapers
Try multiple wait strategies before giving up:
```javascript
const PROFILES = ['domcontentloaded', 'load', 'networkidle'];
for (const waitUntil of PROFILES) {
    try {
        await page.goto(url, { waitUntil, timeout: 30000 });
        return await extractData(page);
    } catch { continue; }
}
return { url, status: 'SCRAPING_FAILED' };
```

---

## Geo-Blocking & Localisation

Many travel sites redirect based on IP or browser language:
1. Set `Accept-Language` header matching the site's locale
2. Set country cookies: `countryCode`, `locale`, `ec-country-settings`
3. If still blocked → need residential proxy in the target country
4. **Max 2 attempts** — if headers + cookies fail, it's IP-based blocking

---

## Validation Protocol

After every scraper run, validate 20+ departures:
1. Select diverse sample (available, sold out, discounted, price extremes, first/last/middle)
2. Navigate to actual site in browser
3. Compare field by field: dates, prices, status
4. Generate pass/fail report
5. If any FAIL → fix and re-validate

---

*Last updated: 2026-02-20*
*Source: WeRoad competitor scraping sessions (7 competitors, 5000+ departures validated)*
