"""Scrape engine — HTTP fast-path, browser fallback, page analysis."""

import asyncio
import inspect
import json
import random
import re
import sys
from typing import Optional, Dict, Any, List

import html2text
import httpx

from debug_logger import debug_logger

# --- Browser fingerprint profiles (coherent UA + headers combos) ---

_PROFILES = [
    {  # Chrome 131 — Windows
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
    {  # Chrome 131 — macOS
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
    },
    {  # Chrome 130 — Windows
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
    {  # Firefox 133 — Windows
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    },
    {  # Firefox 133 — macOS
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:133.0) Gecko/20100101 Firefox/133.0",
    },
    {  # Safari 17.5 — macOS
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    },
    {  # Edge 131 — Windows
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        "Sec-Ch-Ua": '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
    },
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,de;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
]

_REFERERS = [
    "https://www.google.com/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    None,  # sometimes no referer is fine
]


def _random_headers() -> dict:
    """Build a coherent browser fingerprint — all headers match the same browser."""
    profile = random.choice(_PROFILES)
    headers = {
        "User-Agent": profile["User-Agent"],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    # Add Chromium-specific client hints if present
    for key in ("Sec-Ch-Ua", "Sec-Ch-Ua-Mobile", "Sec-Ch-Ua-Platform"):
        if key in profile:
            headers[key] = profile[key]
    # Random referer (looks like organic traffic from search engines)
    ref = random.choice(_REFERERS)
    if ref:
        headers["Referer"] = ref
        headers["Sec-Fetch-Site"] = "cross-site"
    return headers


# --- HTTP fast-path ---


async def http_fetch(url: str, proxy: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Try HTTP-only fetch. Returns dict with html/status/engine or None if quality check fails."""
    try:
        headers = _random_headers()
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30.0,
            proxy=proxy,
        ) as client:
            resp = await client.get(url, headers=headers)

        if resp.status_code >= 400:
            return None

        html = resp.text
        lower = html.lower()

        # Quality check: must have real HTML, not binary garbage
        if len(html) < 500 or "captcha" in lower or "cf-browser-verification" in lower:
            return None
        if "<html" not in lower and "<!doctype" not in lower:
            return None

        return {"html": html, "status": resp.status_code, "engine": "httpx"}
    except Exception as e:
        debug_logger.log_info("scrape_engine", "http_fetch", f"HTTP failed for {url}: {e}")
        return None


# --- Browser fetch (stateless: spawn -> navigate -> extract -> close) ---


async def browser_fetch(
    url: str,
    browser_manager,
    wait_for: Optional[str] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    """Stateless browser fetch. Spawns, navigates, extracts, closes."""
    from models import BrowserOptions

    options = BrowserOptions(
        headless=headless,
        block_resources=["image", "font", "media"],
        viewport_width=1280,
        viewport_height=800,
    )
    instance = await browser_manager.spawn_browser(options)
    instance_id = instance.instance_id

    try:
        tab = await browser_manager.get_tab(instance_id)
        if not tab:
            raise RuntimeError(f"Failed to get tab for {instance_id}")

        await tab.get(url)

        # Wait for DOM content
        await tab.sleep(2)

        # Optional: wait for specific selector
        if wait_for:
            try:
                await asyncio.wait_for(tab.select(wait_for), timeout=10.0)
            except (asyncio.TimeoutError, Exception):
                debug_logger.log_info(
                    "scrape_engine", "browser_fetch", f"wait_for '{wait_for}' timed out"
                )

        # Extra settle time for dynamic content
        await tab.sleep(1)

        html = await tab.evaluate("document.documentElement.outerHTML")
        title = await tab.evaluate("document.title")
        final_url = await tab.evaluate("window.location.href")

        return {"html": html or "", "title": title or "", "url": final_url or url, "engine": "nodriver"}
    finally:
        try:
            await browser_manager.close_instance(instance_id)
        except Exception:
            pass


# --- Playwright-to-nodriver adapter for recipe scripts ---


class _PageAdapter:
    """Wraps a nodriver tab to provide a Playwright-like Page API."""

    def __init__(self, tab):
        self._tab = tab

    async def goto(self, url: str, **kwargs):
        """Navigate to URL. Accepts wait_until/timeout for Playwright compat."""
        await self._tab.get(url)
        await self._tab.sleep(2)  # settle time

    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        """Wait for a CSS selector to appear."""
        try:
            await asyncio.wait_for(
                self._tab.select(selector), timeout=timeout / 1000
            )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Selector '{selector}' not found within {timeout}ms")

    async def evaluate(self, js_code: str):
        """Evaluate JavaScript in page context."""
        return await self._tab.evaluate(js_code)

    async def query_selector(self, selector: str):
        """Query a single element."""
        try:
            return await self._tab.select(selector)
        except Exception:
            return None

    async def query_selector_all(self, selector: str):
        """Query all matching elements."""
        try:
            return await self._tab.select_all(selector)
        except Exception:
            return []

    async def close(self):
        """No-op — cleanup handled by _run_recipe_script's finally block."""
        pass


class _BrowserAdapter:
    """Wraps a nodriver tab to provide a Playwright-like Browser API."""

    def __init__(self, tab):
        self._tab = tab
        self._page = _PageAdapter(tab)

    async def new_page(self):
        """Return the existing page adapter (nodriver uses single-tab model)."""
        return self._page


# --- Smart large-content detection ---

SMART_RESPONSE_THRESHOLD = 50_000  # chars (~12K tokens)


def _extract_tables_from_html(html: str) -> List[Dict[str, Any]]:
    """Parse HTML tables into structured JSON using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[scrape_engine] beautifulsoup4 not installed, skipping table extraction", file=sys.stderr)
        return []

    soup = BeautifulSoup(html, "html.parser")
    tables = []

    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if not headers:
            # Try first row as headers
            first_row = table.find("tr")
            if first_row:
                headers = [td.get_text(strip=True) for td in first_row.find_all(["td", "th"])]

        if not headers:
            continue

        rows = []
        for tr in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if cells and len(cells) == len(headers):
                rows.append(dict(zip(headers, cells)))

        if rows:
            tables.append({
                "columns": headers,
                "total_rows": len(rows),
                "rows": rows,
            })

    return tables


def _build_smart_response(
    url: str, engine: str, html: str, markdown: str, tables: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build compact metadata response for large pages."""
    import tempfile

    response: Dict[str, Any] = {
        "url": url,
        "engine": engine,
        "html_size": len(html),
        "markdown_size": len(markdown),
        "large_content": True,
    }

    if tables:
        # Use the largest table
        main_table = max(tables, key=lambda t: t["total_rows"])
        response["table_detected"] = True
        response["columns"] = main_table["columns"]
        response["total_rows"] = main_table["total_rows"]
        response["sample"] = main_table["rows"][:20]

        # Save full data to temp file
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", prefix="scrapelab_full_",
                delete=False,
            )
            json.dump(main_table["rows"], tmp, ensure_ascii=False, indent=1)
            tmp.close()
            response["full_data_path"] = tmp.name
        except Exception as e:
            print(f"[scrape_engine] Failed to save full data: {e}", file=sys.stderr)

        response["message"] = (
            f"Large table detected ({main_table['total_rows']} rows, "
            f"{len(main_table['columns'])} columns). "
            f"Showing first 20 rows as sample. "
            f"Full data saved to {response.get('full_data_path', 'N/A')}. "
            f"Consider saving a recipe with save_recipe for consistent structured extraction."
        )
    else:
        # No table — return markdown preview
        response["markdown_preview"] = markdown[:5000]
        response["message"] = (
            f"Large page ({len(markdown):,} chars markdown). "
            f"Showing first 5000 chars as preview. "
            f"Consider saving a recipe for structured extraction."
        )

    return response


# --- Smart scrape (main entry point) ---


async def _run_recipe_script(
    script_code: str,
    url: str,
    browser_manager=None,
    headless: bool = True,
) -> Optional[Dict[str, Any]]:
    """Execute a recipe's scrape() function in an isolated namespace.

    Supports two signatures:
      - scrape(url) → pure HTTP script (no browser needed)
      - scrape(browser, url) → browser-based script (spawns a browser instance)

    Returns the dict on success, None on error.
    """
    namespace: Dict[str, Any] = {}
    try:
        exec(script_code, namespace)
    except Exception as e:
        print(f"[recipe_script] exec() failed: {e}", file=sys.stderr)
        debug_logger.log_info("scrape_engine", "recipe_script", f"exec() failed: {e}")
        return None

    scrape_fn = namespace.get("scrape")
    if not callable(scrape_fn):
        print("[recipe_script] No scrape() function found in script", file=sys.stderr)
        debug_logger.log_info("scrape_engine", "recipe_script", "No scrape() function found in script")
        return None

    # Inspect signature to determine call mode
    try:
        sig = inspect.signature(scrape_fn)
        param_count = len(sig.parameters)
    except (ValueError, TypeError):
        param_count = 1  # default to url-only

    needs_browser = param_count >= 2
    print(f"[recipe_script] scrape() has {param_count} params → {'browser+url' if needs_browser else 'url-only'}", file=sys.stderr)

    instance_id = None
    try:
        if needs_browser:
            if browser_manager is None:
                print("[recipe_script] Script needs browser but no browser_manager available", file=sys.stderr)
                return None

            # Spawn a browser for the script
            from models import BrowserOptions
            options = BrowserOptions(
                headless=headless,
                block_resources=["font", "media"],
                viewport_width=1280,
                viewport_height=800,
            )
            instance = await browser_manager.spawn_browser(options)
            instance_id = instance.instance_id
            tab = await browser_manager.get_tab(instance_id)
            if not tab:
                print(f"[recipe_script] Failed to get tab for {instance_id}", file=sys.stderr)
                return None

            # Wrap tab in Playwright-compatible adapter and pass to script
            browser_adapter = _BrowserAdapter(tab)
            result = await asyncio.wait_for(scrape_fn(browser_adapter, url), timeout=90.0)
        else:
            result = await asyncio.wait_for(scrape_fn(url), timeout=60.0)

        if isinstance(result, dict):
            print(f"[recipe_script] Success — got dict with {len(result)} keys", file=sys.stderr)
            return result
        if isinstance(result, list):
            print(f"[recipe_script] Success — got list with {len(result)} items, wrapping in dict", file=sys.stderr)
            return {"data": result}

        print(f"[recipe_script] scrape() returned {type(result)}, expected dict/list", file=sys.stderr)
        debug_logger.log_info("scrape_engine", "recipe_script", f"scrape() returned {type(result)}")
        return None
    except asyncio.TimeoutError:
        print(f"[recipe_script] scrape() timed out after {'90s' if needs_browser else '60s'}", file=sys.stderr)
        debug_logger.log_info("scrape_engine", "recipe_script", "scrape() timed out")
        return None
    except Exception as e:
        print(f"[recipe_script] scrape() raised: {type(e).__name__}: {e}", file=sys.stderr)
        debug_logger.log_info("scrape_engine", "recipe_script", f"scrape() raised: {e}")
        return None
    finally:
        # Clean up browser if we spawned one
        if instance_id and browser_manager:
            try:
                await browser_manager.close_instance(instance_id)
            except Exception:
                pass


async def scrape_smart(
    url: str,
    browser_manager,
    recipe: Optional[Dict[str, Any]] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Smart scrape: recipe script -> HTTP fast-path -> browser fallback.
    Returns dict with structured data (if script), or html/markdown + analysis.
    """

    # Step 0: Recipe has a script with scrape() → execute it directly
    if recipe and recipe.get("script"):
        script_result = await _run_recipe_script(
            recipe["script"], url,
            browser_manager=browser_manager,
            headless=headless,
        )
        if script_result is not None:
            response = {
                "url": url,
                "engine": "recipe_script",
                "recipe_id": recipe.get("id"),
                "data": script_result,
            }
            if recipe.get("schema"):
                response["recipe_schema"] = recipe["schema"]
            return response

    # Extract wait_for from recipe config (nested in config dict)
    config = recipe.get("config", {}) if recipe else {}
    wait_for = recipe.get("wait_for") or config.get("wait_for") if recipe else None
    scrape_level = recipe.get("scrape_level", 1) if recipe else 1

    result = None

    # Step 1: HTTP fast-path (if level allows it)
    if scrape_level <= 1:
        result = await http_fetch(url)

    # Step 2: Browser fallback
    if result is None:
        result = await browser_fetch(url, browser_manager, wait_for=wait_for, headless=headless)

    html = result.get("html", "")
    markdown = html_to_markdown(html)

    # Smart large-content detection: return metadata instead of full markdown
    if len(markdown) > SMART_RESPONSE_THRESHOLD:
        print(f"[scrape_engine] Large content detected ({len(markdown):,} chars), building smart response", file=sys.stderr)
        tables = _extract_tables_from_html(html)
        return _build_smart_response(url, result.get("engine", "unknown"), html, markdown, tables)

    # Build response
    response = {
        "url": url,
        "engine": result.get("engine", "unknown"),
        "html_size": len(html),
        "markdown_size": len(markdown),
    }

    if recipe:
        # Recipe exists but script failed or absent: return markdown + recipe knowledge
        response["recipe_id"] = recipe.get("id")
        if recipe.get("prompt"):
            response["recipe_prompt"] = recipe["prompt"]
        if recipe.get("schema"):
            response["recipe_schema"] = recipe["schema"]
        response["markdown"] = markdown
    else:
        # No recipe: analyze page and return analysis + full markdown
        analysis = analyze_page(html, url)
        analysis["engine"] = result.get("engine", "unknown")
        response["analysis"] = analysis
        response["markdown"] = markdown
        response["message"] = "No recipe for this site. Review the markdown and consider saving a recipe with save_recipe."

    return response


# --- Page analysis ---


def analyze_page(html: str, url: str) -> Dict[str, Any]:
    """Analyze page structure: title, JSON-LD, framework, API endpoints, text preview."""
    result: Dict[str, Any] = {}

    # Title
    m = re.search(r"<title>([^<]+)</title>", html, re.I)
    result["title"] = m.group(1).strip() if m else ""

    # JSON-LD
    json_ld = []
    for m in re.finditer(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>', html, re.I
    ):
        try:
            json_ld.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
    if json_ld:
        result["json_ld"] = json_ld

    # Framework detection
    if "__NEXT_DATA__" in html:
        result["framework"] = "next.js"
    elif "__NUXT__" in html or "nuxt" in html.lower()[:5000]:
        result["framework"] = "nuxt.js"
    elif "_gatsby" in html:
        result["framework"] = "gatsby"
    elif "wp-content" in html or "wp-json" in html:
        result["framework"] = "wordpress"
    elif "shopify" in html.lower()[:10000]:
        result["framework"] = "shopify"

    # API endpoints
    api_matches = re.findall(
        r'["\'](https?://[^"\']*(?:api|graphql)[^"\']*?)["\']', html, re.I
    )
    if api_matches:
        result["api_endpoints"] = list(set(api_matches))[:10]

    # HTML size
    result["html_size"] = len(html)

    # Text preview (cleaned)
    text = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    result["text_preview"] = text[:3000]

    return result


# --- HTML to Markdown ---

_h2t = html2text.HTML2Text()
_h2t.ignore_links = False
_h2t.ignore_images = True
_h2t.ignore_emphasis = False
_h2t.body_width = 0


def html_to_markdown(html: str) -> str:
    """Convert HTML to compact Markdown. Strips nav/footer/script/style first."""
    c = html
    for tag in ("script", "style", "svg", "noscript", "nav", "footer", "header"):
        c = re.sub(rf"<{tag}[\s\S]*?</{tag}>", "", c, flags=re.I)
    c = re.sub(r"<!--[\s\S]*?-->", "", c)
    md = _h2t.handle(c)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip()


def clean_html(html: str) -> str:
    """Remove script, style, svg, noscript, comments. Collapse whitespace."""
    c = html
    c = re.sub(r"<script[\s\S]*?</script>", "", c, flags=re.I)
    c = re.sub(r"<style[\s\S]*?</style>", "", c, flags=re.I)
    c = re.sub(r"<svg[\s\S]*?</svg>", "", c, flags=re.I)
    c = re.sub(r"<noscript[\s\S]*?</noscript>", "", c, flags=re.I)
    c = re.sub(r"<!--[\s\S]*?-->", "", c)
    c = re.sub(r"\s+", " ", c)
    return c.strip()


# --- Batch scrape ---


BATCH_MARKDOWN_PREVIEW = 2000


async def batch_scrape(
    urls: List[str],
    browser_manager,
    recipe: Optional[Dict[str, Any]] = None,
    headless: bool = True,
    max_concurrent_http: int = 5,
) -> List[Dict[str, Any]]:
    """
    Batch scrape multiple URLs.
    Strategy: recipe script (parallel) -> HTTP (parallel) -> browser (sequential).
    If recipe has a script, executes it for all URLs first.
    Returns structured data (if script) or lightweight HTML results.
    """
    results: Dict[str, Dict[str, Any]] = {}
    config = recipe.get("config", {}) if recipe else {}
    wait_for = recipe.get("wait_for") or config.get("wait_for") if recipe else None
    scrape_level = recipe.get("scrape_level", 1) if recipe else 1

    remaining = list(urls)

    # Phase 0: Recipe script (parallel for HTTP-only scripts)
    if recipe and recipe.get("script"):
        script_code = recipe["script"]

        # Check if script needs browser
        namespace: Dict[str, Any] = {}
        try:
            exec(script_code, namespace)
            scrape_fn = namespace.get("scrape")
            if scrape_fn and callable(scrape_fn):
                sig = inspect.signature(scrape_fn)
                needs_browser = len(sig.parameters) >= 2
            else:
                needs_browser = False
        except Exception:
            needs_browser = False

        if not needs_browser:
            # HTTP-only script → run all in parallel
            semaphore = asyncio.Semaphore(max_concurrent_http)

            async def try_script(u: str):
                async with semaphore:
                    r = await _run_recipe_script(script_code, u)
                    return u, r

            script_tasks = [try_script(u) for u in remaining]
            script_results = await asyncio.gather(*script_tasks, return_exceptions=True)

            still_remaining = []
            for item in script_results:
                if isinstance(item, Exception):
                    continue
                u, r = item
                if r is not None:
                    results[u] = {
                        "url": u,
                        "engine": "recipe_script",
                        "recipe_id": recipe.get("id"),
                        "data": r,
                    }
                else:
                    still_remaining.append(u)

            remaining = still_remaining
            print(f"[batch] Phase 0 (script): {len(results)} ok, {len(remaining)} remaining", file=sys.stderr)
        else:
            # Browser-based script → run sequentially
            still_remaining = []
            for u in remaining:
                r = await _run_recipe_script(
                    script_code, u,
                    browser_manager=browser_manager,
                    headless=headless,
                )
                if r is not None:
                    results[u] = {
                        "url": u,
                        "engine": "recipe_script",
                        "recipe_id": recipe.get("id"),
                        "data": r,
                    }
                else:
                    still_remaining.append(u)
            remaining = still_remaining
            print(f"[batch] Phase 0 (browser script): {len(results)} ok, {len(remaining)} remaining", file=sys.stderr)

    if not remaining:
        return [results.get(u, {"url": u, "error": "not processed"}) for u in urls]

    # Phase 1: parallel HTTP for remaining URLs (if level allows)
    if scrape_level <= 1:
        semaphore = asyncio.Semaphore(max_concurrent_http)

        async def try_http(url: str):
            async with semaphore:
                return url, await http_fetch(url)

        http_tasks = [try_http(u) for u in remaining]
        http_results = await asyncio.gather(*http_tasks, return_exceptions=True)

        still_remaining = []
        for item in http_results:
            if isinstance(item, Exception):
                continue
            u, result = item
            if result is not None:
                results[u] = _build_batch_result(u, result["html"], "httpx", recipe)
            else:
                still_remaining.append(u)
        remaining = still_remaining

    # Phase 2: sequential browser for remaining
    for u in remaining:
        try:
            result = await browser_fetch(u, browser_manager, wait_for=wait_for, headless=headless)
            results[u] = _build_batch_result(u, result["html"], "nodriver", recipe)
        except Exception as e:
            results[u] = {"url": u, "error": str(e)}

    return [results.get(u, {"url": u, "error": "not processed"}) for u in urls]


def _build_batch_result(
    url: str, html: str, engine: str, recipe: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build a lightweight batch result: analysis + markdown preview (no full markdown)."""
    markdown = html_to_markdown(html)
    analysis = analyze_page(html, url)
    analysis["engine"] = engine

    entry: Dict[str, Any] = {
        "url": url,
        "engine": engine,
        "html_size": len(html),
        "markdown_size": len(markdown),
        "analysis": analysis,
        "markdown_preview": markdown[:BATCH_MARKDOWN_PREVIEW],
    }
    if recipe:
        entry["recipe_id"] = recipe.get("id")
    return entry
