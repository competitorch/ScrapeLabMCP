# DOM Scraping with Playwright — Knowledge Base

> Referenced from [agent.md](./agent.md) when no API is available and you must scrape rendered HTML.

---

## When to Use

- No REST/GraphQL API found during reconnaissance
- Data is rendered by JavaScript in the browser
- Site uses heavy client-side rendering (React, Vue SPA without SSR data)

**This is the last resort.** DOM scrapers are the most fragile, slowest, and most resource-hungry approach.

---

## Resource Blocking (MANDATORY)

Every DOM scraper MUST block unnecessary resources to save memory and speed up loading:

```javascript
await page.route('**/*', (route) => {
    const type = route.request().resourceType();
    if (['image', 'media', 'font', 'stylesheet'].includes(type)) {
        return route.abort();
    }
    return route.continue();
});
```

**Impact:** 2-3x faster page loads, 40-60% less memory usage.

---

## Profile Fallback Strategy

Sites behave differently — try multiple wait strategies:

```javascript
const PROFILES = ['domcontentloaded', 'load', 'networkidle'];

async function loadPage(page, url) {
    for (const waitUntil of PROFILES) {
        try {
            await page.goto(url, { waitUntil, timeout: 30000 });
            // Verify content loaded
            const hasContent = await page.$('.departure-card');
            if (hasContent) return true;
        } catch (err) {
            console.warn(`Profile ${waitUntil} failed: ${err.message}`);
        }
    }
    return false;
}
```

**Key insight:** Start with `domcontentloaded` (fastest) and only fall back to slower profiles if content isn't there yet.

---

## Concurrency vs RAM

Playwright browsers are memory-hungry. Match concurrency to available RAM:

| RAM | maxConcurrency | Notes |
|-----|---------------|-------|
| 1 GB (Apify free) | **2** | Tested: 10 crashes, 3 marginal, 2 stable |
| 2 GB | 3-4 | Safe zone |
| 4 GB | 5-8 | Good performance |
| 8 GB | 10-15 | Optimal |

**Real-world lesson:** On Apify free tier (1GB), maxConcurrency=10 caused 9/10 pages to timeout. Reducing to 2 fixed everything.

---

## Waiting for Dynamic Content

### Wait for specific selector
```javascript
await page.waitForSelector('.departure-card', { timeout: 10000 });
```

### Wait for network to settle
```javascript
await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
```

### Wait for JavaScript condition
```javascript
await page.waitForFunction(() => {
    return document.querySelectorAll('.departure-card').length > 0;
}, { timeout: 10000 });
```

### Click to reveal content (modals, tabs)
```javascript
// Click a button to open departure dates
await page.click('button:has-text("See dates")', { timeout: 5000 });
await page.waitForSelector('.dates-modal .departure-row', { timeout: 10000 });
```

---

## Responsive Layout Deduplication

Many sites render BOTH mobile and desktop views in the same DOM:

```html
<!-- Desktop version -->
<div class="d-none d-md-block">
    <div class="departure-card">...</div>
</div>
<!-- Mobile version (duplicate!) -->
<div class="d-block d-md-none">
    <div class="departure-card">...</div>
</div>
```

**Detection patterns:**
- Bootstrap: `.d-none.d-md-block` / `.d-block.d-md-none`
- Custom: `.desktop-only` / `.mobile-only`
- Fresnel (responsive): `.fresnel-greaterThanOrEqual-md` / `.fresnel-lessThan-md`

**Fix:** Always filter by the desktop container, or deduplicate results by unique key (date + tour name).

---

## Selector Resilience

**Fragile (will break):**
```javascript
'.css-1abc23'           // Generated class hash
'.sc-bdVTJa'            // Styled-components hash
'div > div > div > span' // Structural path
```

**Resilient (prefer these):**
```javascript
'[data-testid="departure-date"]'    // Test IDs
'[itemprop="price"]'                 // Schema.org
'time[datetime]'                     // Semantic HTML
'button:has-text("Book")'           // Text content
'.departure-card'                    // Semantic class names
```

---

## Common DOM Scraping Patterns

### Extract departure cards
```javascript
const cards = await page.$$('.departure-card');
const departures = [];
for (const card of cards) {
    departures.push({
        date: await card.$eval('.date', el => el.textContent.trim()).catch(() => ''),
        price: await card.$eval('.price', el => el.textContent.trim()).catch(() => ''),
        status: await card.$eval('.status', el => el.textContent.trim()).catch(() => 'Available'),
    });
}
```

### Handle lazy-loaded content
```javascript
// Scroll to bottom to trigger lazy loading
await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
await page.waitForTimeout(2000);

// Or click "Load more" until exhausted
while (true) {
    const btn = await page.$('button.load-more');
    if (!btn) break;
    await btn.click();
    await page.waitForTimeout(1500);
}
```

---

## Real-World Examples

### Copines de Voyage (DOM + Dynamic Catalogue)
- Catalogue discovery: fetch `/catalogue.data?page=N` for slugs
- Departures: Playwright renders `/offre/{slug}/departs`
- Key issue: Fresnel responsive containers create duplicates
- maxConcurrency: 2 (Apify 1GB)
- Push every 10 URLs using counter pattern

### Sivola (DOM + Sitemap + Modal)
- Discovery: `/sitemap/products.xml`
- Departures behind modal: click "Vedi le partenze", wait 5s
- Cards: `div.card-home[data-cw--calendar-date]`
- Price: `span.d-block.font-weight-bolder.h5.mb-0`

### Huakai (DOM + Pagination)
- Discovery: `/buscar-viajes/page/N/`
- Pagination: `.tourmaster-pagination`
- European price format: `1.397€` → `"1397"`

### Avventure nel Mondo (DOM + Sitemap)
- Discovery: `/sitemap.xml` → `/viaggi/\d+`
- Departure rows: `div.base__date[data-cod]`
- Italian months, year inferred from context

---

*Last updated: 2026-02-20*
