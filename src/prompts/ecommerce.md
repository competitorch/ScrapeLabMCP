# E-Commerce Site Scraping — Knowledge Base

> Referenced from [agent.md](./agent.md) for e-commerce platforms.

---

## Platform Detection

Before scraping, identify the platform:

```bash
# Quick platform detection
curl -s "URL" | grep -iE "shopify|woocommerce|magento|prestashop|bigcommerce|squarespace" | head -5
```

| Clue in HTML | Platform |
|-------------|----------|
| `cdn.shopify.com`, `myshopify.com` | Shopify |
| `wp-content`, `woocommerce` | WooCommerce (WordPress) |
| `Magento`, `mage/cookies` | Magento |
| `prestashop` | PrestaShop |
| `bigcommerce` | BigCommerce |
| `squarespace.com` | Squarespace |

---

## Shopify

### Product data (easiest)
```bash
# All products as JSON (up to 250 per page)
curl -s "https://store.com/products.json?limit=250&page=1"

# Collection products
curl -s "https://store.com/collections/{handle}/products.json?limit=250"

# Single product
curl -s "https://store.com/products/{handle}.json"
```

### Scraping pattern
```javascript
import { gotScraping } from 'got-scraping';

let page = 1;
let products = [];
while (true) {
    const { body } = await gotScraping({
        url: `https://store.com/products.json?limit=250&page=${page}`,
        responseType: 'json',
    });
    if (!body.products || body.products.length === 0) break;
    products.push(...body.products);
    page++;
}
```

### Key fields
- `product.title` — product name
- `product.variants[].price` — price (as string with decimals: "29.99")
- `product.variants[].compare_at_price` — original price (if discounted)
- `product.variants[].available` — in stock boolean
- `product.handle` — URL slug
- `product.tags` — array of tags

### Gotchas
- `/products.json` may be disabled — check with curl first
- Some stores geo-redirect based on IP — set country cookies
- Prices include decimals: `"29.99"` → clean to `"30"` or `"2999"` depending on format needed
- Variants: a product can have multiple variants (sizes, colors) with different prices

---

## WooCommerce

See [wordpress.md](./wordpress.md) for WP REST API details.

### Product API
```bash
# WooCommerce REST API (if public)
curl -s "https://store.com/wp-json/wc/v3/products?per_page=100&page=1"
# Often requires consumer_key/consumer_secret

# Alternative: standard WP REST API
curl -s "https://store.com/wp-json/wp/v2/product?per_page=100&page=1"
```

### Fallback to DOM
If API is locked down, scrape product listing pages with Playwright. Look for:
- `.product-card`, `.woocommerce-loop-product__title`
- Price: `.woocommerce-Price-amount`
- Sale price: `del .woocommerce-Price-amount` (original) + `ins .woocommerce-Price-amount` (sale)

---

## Magento

### API access
```bash
# Magento 2 REST API (often requires auth token)
curl -s "https://store.com/rest/V1/products?searchCriteria[pageSize]=50&searchCriteria[currentPage]=1" \
  -H "Authorization: Bearer TOKEN"

# GraphQL (Magento 2.3+)
curl -s "https://store.com/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ products(search: \"\", pageSize: 50) { items { name sku price_range { minimum_price { regular_price { value } } } } } }"}'
```

### Fallback selectors
- Product cards: `.product-item`, `.product-items li`
- Price: `.price-box .price`
- Old price: `.price-box .old-price .price`
- Availability: `.stock.available`, `.stock.unavailable`

---

## Universal E-Commerce Patterns

### Price extraction
```javascript
function cleanEcommercePrice(raw) {
    if (!raw) return '';
    // Remove currency symbols, whitespace
    let cleaned = raw.replace(/[€$£¥₹\s]/g, '');
    // Handle European format: 1.234,56 → 1234.56
    if (/\d+\.\d{3}/.test(cleaned) && cleaned.includes(',')) {
        cleaned = cleaned.replace(/\./g, '').replace(',', '.');
    }
    // Handle comma as decimal: 29,99 → 29.99
    else if (/^\d+,\d{2}$/.test(cleaned)) {
        cleaned = cleaned.replace(',', '.');
    }
    return String(Math.round(parseFloat(cleaned)));
}
```

### Availability detection
Common text/class patterns across platforms:
```javascript
function detectAvailability(element) {
    const text = element.textContent.toLowerCase();
    const classes = element.className.toLowerCase();

    if (text.match(/sold out|out of stock|esaurito|agotado|indisponible|ausverkauft/))
        return 'SOLDOUT';
    if (text.match(/available|in stock|disponibile|disponible|verfügbar/))
        return 'AVAILABLE';
    if (classes.includes('unavailable') || classes.includes('out-of-stock'))
        return 'SOLDOUT';

    return 'AVAILABLE'; // default assumption
}
```

### Pagination
Most e-commerce sites use one of:
1. **URL-based:** `/products/page/2/`, `?page=2`, `?p=2`
2. **"Load more" button:** Click to append items
3. **Infinite scroll:** Scroll triggers API calls
4. **API pagination:** JSON endpoint with `page` + `per_page` params

Always check the **total product count** displayed on the page and verify your scraper captures the same number.

---

## Structured Data (Schema.org)

E-commerce sites often have `<script type="application/ld+json">` with product data. However:

> **WARNING:** JSON-LD is SEO metadata, NOT the user-visible content. It may be outdated, incomplete, or different from what's shown on the page. ALWAYS prefer visible DOM data or API data over JSON-LD.

Only use JSON-LD as a last resort, and always cross-validate with what's visible on the page.

---

*Last updated: 2026-02-20*
