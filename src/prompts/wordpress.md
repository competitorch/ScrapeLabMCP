# WordPress Site Scraping — Knowledge Base

> Referenced from [agent.md](./agent.md) for WordPress-based sites.

---

## Detection

```bash
# Quick WordPress detection
curl -sI "URL" | grep -i "x-powered-by\|wp-"
curl -s "URL" | grep -c "wp-content"
curl -s "URL/wp-json/" | head -20
```

Signs:
- `/wp-content/` in HTML source
- `/wp-json/` endpoint accessible
- `X-Powered-By: WordPress` header (not always present)
- `/xmlrpc.php` exists

---

## API-First Approach (ALWAYS TRY THIS FIRST)

### WP REST API
```bash
# Check if REST API is accessible
curl -s "https://site.com/wp-json/wp/v2/" | jq '.routes | keys'

# List available post types
curl -s "https://site.com/wp-json/wp/v2/types" | jq 'keys'

# Fetch posts (default post type)
curl -s "https://site.com/wp-json/wp/v2/posts?per_page=100&page=1"

# Fetch custom post type (e.g., "tour", "product", "trip")
curl -s "https://site.com/wp-json/wp/v2/tour?per_page=100&page=1"
```

### Pagination
WP REST API returns pagination headers:
- `X-WP-Total`: total items
- `X-WP-TotalPages`: total pages

```javascript
import { gotScraping } from 'got-scraping';

async function fetchAllPosts(baseUrl, postType = 'posts') {
    const all = [];
    let page = 1;
    while (true) {
        const response = await gotScraping({
            url: `${baseUrl}/wp-json/wp/v2/${postType}?per_page=100&page=${page}`,
            responseType: 'json',
        });
        all.push(...response.body);
        const totalPages = parseInt(response.headers['x-wp-totalpages'], 10);
        if (page >= totalPages) break;
        page++;
    }
    return all;
}
```

### Custom Fields
WordPress plugins (ACF, Pods, etc.) add custom fields. These often appear in the REST API response under `acf`, `meta`, or custom keys:
```javascript
const post = response.body[0];
// Standard fields
post.title.rendered    // Post title (HTML)
post.content.rendered  // Post content (HTML)
post.date              // Publication date
post.link              // Permalink

// Custom fields (ACF)
post.acf.price         // Custom field
post.acf.departure_date
```

---

## Admin AJAX Fallback

If the REST API is restricted, many WP sites use `admin-ajax.php`:

```bash
# Discover AJAX actions from page source
curl -s "URL" | grep -oE 'action["\s:]*["'\'']\w+' | sort -u
```

```javascript
const { body } = await gotScraping({
    url: 'https://site.com/wp-admin/admin-ajax.php',
    method: 'POST',
    form: {
        action: 'load_tours',    // AJAX action name
        page: '1',
        nonce: nonceValue,       // If required
    },
    responseType: 'json',
});
```

### Finding the nonce
If AJAX requires a nonce, it's usually embedded in the page:
```bash
curl -s "URL" | grep -oE 'nonce["\s:]*["'\'']\w+' | head -5
```

---

## Sitemap Discovery

WordPress sitemaps are great for URL discovery:

```bash
# Default WordPress sitemap (WP 5.5+)
curl -s "https://site.com/wp-sitemap.xml"

# Yoast SEO sitemap
curl -s "https://site.com/sitemap_index.xml"

# Rank Math sitemap
curl -s "https://site.com/sitemap_index.xml"
```

```javascript
import { gotScraping } from 'got-scraping';
import { parseStringPromise } from 'xml2js';

async function getWPSitemapUrls(sitemapUrl, pattern) {
    const { body } = await gotScraping({ url: sitemapUrl });
    const parsed = await parseStringPromise(body);

    // Handle sitemap index (has sub-sitemaps)
    if (parsed.sitemapindex) {
        const subSitemaps = parsed.sitemapindex.sitemap.map(s => s.loc[0]);
        const allUrls = [];
        for (const sub of subSitemaps) {
            const subUrls = await getWPSitemapUrls(sub, pattern);
            allUrls.push(...subUrls);
        }
        return allUrls;
    }

    // Handle urlset (actual URLs)
    return parsed.urlset.url
        .map(u => u.loc[0])
        .filter(url => pattern.test(url));
}
```

---

## WooCommerce Specifics

See [ecommerce.md](./ecommerce.md) for full e-commerce patterns.

```bash
# WooCommerce REST API (often needs auth)
curl -s "https://site.com/wp-json/wc/v3/products?per_page=100" \
  -u "consumer_key:consumer_secret"

# Public product endpoint (if available)
curl -s "https://site.com/wp-json/wp/v2/product?per_page=100"
```

---

## DOM Fallback Selectors

If no API is available, common WordPress theme selectors:

```javascript
// Blog posts
'.post', '.entry', 'article.hentry'
'.entry-title a'           // Title + link
'.entry-content'           // Content
'.post-date', '.entry-date' // Date

// WooCommerce products
'.product', '.woocommerce-loop-product'
'.woocommerce-loop-product__title'
'.woocommerce-Price-amount'
'.stock'
```

---

## Common Gotchas

### REST API disabled
Some sites disable the WP REST API. Check:
```bash
curl -s "https://site.com/wp-json/" | head -5
# If 404 or empty → API disabled
# Try: /wp-json/wp/v2/posts?per_page=1 specifically
```

### Password-protected content
Posts marked as private or password-protected won't appear in API responses without authentication.

### Multisite installations
WordPress Multisite may have different API paths: `/blog/wp-json/...`, `/subsite/wp-json/...`

### Caching plugins
Some caching plugins (WP Super Cache, W3 Total Cache) may serve stale content. Add `?nocache=1` or vary the URL slightly.

---

*Last updated: 2026-02-20*
