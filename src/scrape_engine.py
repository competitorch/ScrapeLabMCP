"""Scrape engine — HTTP fast-path, browser fallback, page analysis."""

import asyncio
import json
import random
import re
from typing import Optional, Dict, Any, List

import html2text
import httpx

from debug_logger import debug_logger

# --- User-Agent rotation ---

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "it-IT,it;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,it;q=0.8",
]


def _random_headers() -> dict:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
    }


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


# --- Smart scrape (main entry point) ---


async def scrape_smart(
    url: str,
    browser_manager,
    recipe: Optional[Dict[str, Any]] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Smart scrape: recipe check -> HTTP fast-path -> browser fallback.
    Returns dict with html, engine, analysis or recipe_prompt.
    """
    wait_for = recipe.get("wait_for") if recipe else None
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

    # Build response
    response = {
        "url": url,
        "engine": result.get("engine", "unknown"),
        "html_size": len(html),
        "markdown_size": len(markdown),
    }

    if recipe:
        # Recipe exists: return markdown + recipe knowledge
        response["recipe_id"] = recipe.get("id")
        response["recipe_slug"] = recipe.get("_slug", "")
        if recipe.get("prompt"):
            response["recipe_prompt"] = recipe["prompt"]
        if recipe.get("script"):
            response["recipe_script"] = recipe["script"]
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
    Strategy: try all URLs with HTTP in parallel first, then browser for failures.
    Returns lightweight results (analysis + markdown_preview) to stay under MCP size limits.
    Use scrape_smart() on individual URLs for full markdown content.
    """
    results: Dict[str, Dict[str, Any]] = {}
    wait_for = recipe.get("wait_for") if recipe else None

    # Phase 1: parallel HTTP for all URLs
    semaphore = asyncio.Semaphore(max_concurrent_http)

    async def try_http(url: str):
        async with semaphore:
            return url, await http_fetch(url)

    http_tasks = [try_http(u) for u in urls]
    http_results = await asyncio.gather(*http_tasks, return_exceptions=True)

    browser_needed = []
    for item in http_results:
        if isinstance(item, Exception):
            continue
        url, result = item
        if result is not None:
            results[url] = _build_batch_result(url, result["html"], "httpx", recipe)
        else:
            browser_needed.append(url)

    # Phase 2: sequential browser for failures
    for url in browser_needed:
        try:
            result = await browser_fetch(url, browser_manager, wait_for=wait_for, headless=headless)
            results[url] = _build_batch_result(url, result["html"], "nodriver", recipe)
        except Exception as e:
            results[url] = {"url": url, "error": str(e)}

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
