<div align="center">

<img src="media/scrapelab-logo.svg" alt="ScrapeLab MCP" width="360"/>

# ScrapeLab MCP

**Smart web scraping for AI agents. Scrape once, learn forever.**

An MCP server that gives Claude (or any MCP client) intelligent scraping capabilities: a recipe system that learns how to scrape sites, an undetectable stealth browser, and HTTP-first speed — all behind a single `scrape_url` tool.

[![MCP](https://img.shields.io/badge/MCP-Compatible-F77F00?style=flat-square)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-F77F00?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-F77F00?style=flat-square)](https://python.org)

</div>

---

## Why ScrapeLab?

Claude can already browse the web. So why use this?

### The Problem

Every time you ask Claude to scrape a site, it starts from zero: navigates the page, reads the full HTML, reasons about the structure, extracts data. This is **slow** (15-30s per URL), **expensive** (50K+ tokens of HTML in context), and **inconsistent** (different formats each time).

### The Solution

ScrapeLab MCP introduces **recipes** — saved scraping strategies with reusable scripts. The first time you scrape a site, Claude analyzes it and creates a recipe. From the second time on, the recipe script executes directly — no browser, no LLM reasoning, just structured data in 1-2 seconds.

```
First time:  URL → analyze → create recipe → data     (~15s, LLM-assisted)
Every time after:  URL → recipe script → data          (~1-2s, zero LLM tokens)
```

### ScrapeLab MCP vs Native Claude

| | Claude (native) | Claude + Chrome MCP | ScrapeLab MCP |
|---|---|---|---|
| **Speed (1 URL)** | ~15-20s | ~15-20s | **~1-2s** (recipe) |
| **Speed (50 URLs)** | ~15 min | ~15 min | **~15s** (parallel batch) |
| **Tokens per URL** | ~50K (full HTML in context) | ~50K | **~2K** (structured JSON only) |
| **Cost (100 URLs/week)** | ~$15/week | ~$15/week | **~$0** (scripts, no LLM) |
| **Output consistency** | Different every time | Different every time | **Identical schema** always |
| **Context window** | Fills up after ~20 URLs | Fills up after ~20 URLs | **Unlimited** (scripts run outside LLM) |
| **Anti-bot bypass** | N/A | Uses real Chrome | **Stealth nodriver** (undetectable) |
| **Learns from past scrapes** | No | No | **Yes** (recipe system) |

---

## How It Works

```
scrape_url("https://news.ycombinator.com/")
│
├── Recipe found? Has script?
│   └── YES → Execute script directly → structured JSON     ⚡ ~1s
│
├── No script → Try HTTP fast-path
│   └── httpx + header rotation → quality check → markdown   ⚡ ~1-3s
│
└── HTTP failed → Stealth browser fallback
    └── nodriver → navigate → render JS → extract            🐢 ~5-15s
```

**Three engines, automatic fallback.** Always picks the fastest one that works.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/competitorch/scrapeLabMCP_BrowserStealth.git
cd scrapeLabMCP_BrowserStealth
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure recipe database (optional)

Recipes can be stored in Supabase for persistence and team sharing:

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_KEY="your-service-role-key"
```

Without Supabase, recipes are stored locally and work fine for single-user setups.

### 3. Add to your MCP client

**Claude Desktop** — add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "scrapelab-mcp": {
      "command": "/path/to/scrapeLabMCP_BrowserStealth/.venv/bin/python",
      "args": ["/path/to/scrapeLabMCP_BrowserStealth/src/server.py"],
      "env": {
        "SUPABASE_URL": "https://your-project.supabase.co",
        "SUPABASE_SERVICE_KEY": "your-key"
      }
    }
  }
}
```

**Claude Code CLI:**

```bash
claude mcp add-json scrapelab-mcp '{
  "type": "stdio",
  "command": "/path/to/.venv/bin/python",
  "args": ["/path/to/src/server.py"]
}'
```

### 4. Try it

```
You: "Scrape https://news.ycombinator.com and get the top 30 posts with title, score, and URL"
```

First time: Claude analyzes the page, writes a scraping script, saves a recipe.
Second time: instant structured data, zero browser, zero reasoning.

---

## Core Features

### Recipe System

Recipes store **how** to scrape a site. Each recipe can contain:

- **Prompt** — extraction instructions for the LLM
- **Script** — a Python `scrape(url)` function that runs directly (no LLM needed)
- **Schema** — JSON schema for structured output validation
- **Config** — scrape level, wait selectors, proxy settings

```python
# Example: recipe script for Hacker News
import httpx
async def scrape(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        ids = resp.json()[:30]
        items = [await client.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json") for i in ids]
        return {"posts": [r.json() for r in items]}
```

Recipes are versioned automatically — every update saves the previous version.

### Batch Scraping

Scrape multiple URLs in parallel with automatic recipe matching:

```
You: "Batch scrape these 10 product pages from the site"
```

The batch engine runs all recipe scripts in parallel (~2-3s for 10 URLs) with automatic fallback to HTTP/browser for failures.

### Stealth Browser

When a site needs JavaScript rendering, ScrapeLab spawns an **undetectable** browser powered by [nodriver](https://github.com/ultrafunkamsterdam/nodriver):

- Passes Cloudflare, DataDome, and other anti-bot systems
- Not Playwright, not Selenium — truly undetectable
- Full Chrome DevTools Protocol (CDP) access
- Network interception with dynamic Python hooks

### Dual-Signature Scripts

Recipe scripts support two modes, detected automatically:

```python
# HTTP-only (no browser needed) — runs in parallel
async def scrape(url: str) -> dict: ...

# Browser-based (spawns stealth browser) — runs sequentially
async def scrape(browser, url: str) -> dict:
    page = await browser.new_page()
    await page.goto(url)
    ...
```

---

## Tools Reference

### Scraping (core)

| Tool | Description |
|------|-------------|
| `scrape_url` | Smart scrape: recipe → HTTP → browser fallback. **Always use this first.** |
| `discover_url` | Analyze a page before scraping (framework, JSON-LD, API endpoints) |
| `batch_scrape_urls` | Parallel scrape with automatic recipe matching |
| `save_recipe` | Save a scraping strategy + script + schema for a site |
| `list_recipes` | List all saved recipes and available knowledge |
| `recipe_history` | View version history of a recipe |
| `delete_recipe` | Remove a recipe |
| `get_specialist_recipe` | Expert guides: api-rest, api-graphql, ecommerce, wordpress... |
| `get_output_schema` | JSON schemas: generic, travel, ecommerce |

### Browser Automation (98 tools)

Full stealth browser control for when you need manual interaction.

<details>
<summary><strong>Browser Management</strong></summary>

`spawn_browser` · `navigate` · `close_instance` · `list_instances` · `get_instance_state` · `go_back` · `go_forward` · `reload_page` · `take_screenshot` · `get_page_content`

</details>

<details>
<summary><strong>Element Interaction</strong></summary>

`query_elements` · `click_element` · `type_text` · `paste_text` · `scroll_page` · `wait_for_element` · `execute_script` · `select_option` · `get_element_state`

</details>

<details>
<summary><strong>Element Extraction (CDP-accurate)</strong></summary>

`extract_complete_element_cdp` · `clone_element_complete` · `extract_element_styles` · `extract_element_structure` · `extract_element_events` · `extract_element_animations` · `extract_element_assets` · `extract_related_files`

</details>

<details>
<summary><strong>Network Interception & Hooks</strong></summary>

`list_network_requests` · `get_request_details` · `get_response_content` · `modify_headers` · `create_dynamic_hook` · `create_simple_dynamic_hook` · `list_dynamic_hooks`

</details>

<details>
<summary><strong>CDP Functions</strong></summary>

`execute_cdp_command` · `discover_global_functions` · `call_javascript_function` · `inject_and_execute_script` · `create_persistent_function` · `execute_python_in_browser`

</details>

<details>
<summary><strong>Progressive Cloning</strong></summary>

`clone_element_progressive` · `expand_styles` · `expand_events` · `expand_children` · `expand_css_rules` · `expand_pseudo_elements` · `expand_animations`

</details>

### Modular Configuration

Run the full suite or strip it down:

```bash
python src/server.py --minimal                # Core tools only
python src/server.py --disable-cdp-functions   # No CDP tools
python src/server.py --list-sections           # See all sections
```

---

## Real-World Example

Monitoring prices across 5 e-commerce product pages:

```
You: "Batch scrape these 5 product URLs and extract name, price, availability"
```

**Result** (2-3 seconds, zero browser):

| Product Page | Items | Engine |
|------|-----------|--------|
| Electronics Store — Laptops | 24 | recipe_script |
| Electronics Store — Phones | 18 | recipe_script |
| Electronics Store — Tablets | 12 | recipe_script |
| Electronics Store — Monitors | 31 | recipe_script |
| Electronics Store — Audio | 15 | recipe_script |

**100 products** extracted in parallel via API, structured JSON, consistent schema.

The same task without ScrapeLab would take Claude ~5 minutes, ~250K tokens, and produce inconsistent output.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP Client                         │
│              (Claude Desktop / Code)                 │
└──────────────────────┬──────────────────────────────┘
                       │ MCP Protocol (stdio)
┌──────────────────────▼──────────────────────────────┐
│                 ScrapeLab MCP Server                 │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Recipe DB │  │ Scrape Engine│  │Stealth Browser│  │
│  │(Supabase) │  │  (3 engines) │  │  (nodriver)   │  │
│  └──────────┘  └──────────────┘  └───────────────┘  │
│                                                      │
│  ┌──────────────┐  ┌─────────┐  ┌────────────────┐  │
│  │Network Hooks │  │CDP Tools│  │Element Cloning │  │
│  └──────────────┘  └─────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## Troubleshooting

**No compatible browser found** — Install Chrome, Chromium, or Edge. Run `validate_browser_environment_tool()` to diagnose.

**Too many tools** — Use `--minimal` or selectively disable sections.

**batch_scrape_urls output too large** — Batch returns structured data when recipes have scripts. For sites without recipes, it returns lightweight previews.

---

## Contributors

Built by [ScrapeLab](https://github.com/competitorch) · [Edoardo Nardi](https://github.com/edoardo-nardi)

Stealth browser engine forked from [nicholishen/nodriver-mcp](https://github.com/nicholishen/nodriver-mcp).

---

## License

MIT — see [LICENSE](LICENSE).
