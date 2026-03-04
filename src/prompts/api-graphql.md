# GraphQL API Scraping — Knowledge Base

> Referenced from [agent.md](./agent.md) when a site uses GraphQL.

---

## When to Use

- Network tab shows POST requests to `/graphql`, `/api/graphql`, or similar
- Request body contains `{"query": "...", "variables": {...}}`
- Response has `{"data": {...}}` structure

---

## Discovery

### 1. Find the endpoint
```bash
# Search for GraphQL endpoint in page source
curl -s "URL" | grep -oE '"[^"]*graphql[^"]*"' | sort -u
```

### 2. Inspect queries in DevTools
- Network tab → filter "graphql" → look at Request Payload
- Copy the full query + variables
- The `operationName` tells you what data it fetches

### 3. Introspection (if enabled)
```bash
curl -s "https://api.example.com/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ __schema { types { name fields { name type { name } } } } }"}' | jq '.data.__schema.types[] | select(.name | startswith("__") | not)'
```

---

## Scraping Pattern

```javascript
import { gotScraping } from 'got-scraping';

async function graphqlQuery(query, variables = {}) {
    const { body } = await gotScraping({
        url: 'https://api.example.com/graphql',
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables }),
        responseType: 'json',
    });
    if (body.errors) {
        throw new Error(`GraphQL errors: ${JSON.stringify(body.errors)}`);
    }
    return body.data;
}

// List all items
const LIST_QUERY = `
    query ListTrips {
        trips {
            id
            code
            title
            url
        }
    }
`;

// Get departures for one item
const DEPARTURES_QUERY = `
    query GetDepartures($tripId: ID!, $currency: String!) {
        trip(id: $tripId) {
            departures(currency: $currency) {
                startDate
                endDate
                price
                discountedPrice
                availableSpaces
                status
            }
        }
    }
`;
```

---

## Pagination in GraphQL

### Relay-style (cursor-based)
```graphql
query ($cursor: String) {
    products(first: 50, after: $cursor) {
        edges {
            node { id name price }
        }
        pageInfo {
            hasNextPage
            endCursor
        }
    }
}
```

```javascript
let cursor = null;
let hasNext = true;
while (hasNext) {
    const data = await graphqlQuery(QUERY, { cursor });
    results.push(...data.products.edges.map(e => e.node));
    hasNext = data.products.pageInfo.hasNextPage;
    cursor = data.products.pageInfo.endCursor;
}
```

### Offset-based
```graphql
query ($offset: Int!, $limit: Int!) {
    products(offset: $offset, limit: $limit) {
        items { id name price }
        total
    }
}
```

---

## Common Gotchas

### Query complexity limits
Some APIs reject queries that are "too complex" (too many nested fields or too deep).
**Fix:** Simplify query, request fewer fields, or split into multiple smaller queries.

### Required variables
**Problem:** Query works in browser but fails in scraper because browser sends variables from app state.
**Fix:** Always copy the full variables object from DevTools, not just the query.

### Currency/locale as variable
**Problem:** Prices come back in wrong currency.
**Fix:** Always pass `currency: "eur"` or equivalent. Check the browser request for locale variables.

---

## Real-World Example

### Flashpack (GraphQL)
- Endpoint: `https://api.flashpack.com/`
- List trips: `{ trips { id code title url } }`
- Departures: query per trip with `currency: "eur"` variable
- No pagination needed (all trips returned at once)
- Concurrency: 15-20 (API is fast, no rate limiting)

---

*Last updated: 2026-02-20*
