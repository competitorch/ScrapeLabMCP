<div align="center">

<img src="media/logo_mcp1.png" alt="ScrapeLab MCP" width="500"/>

# ScrapeLab MCP

**The most complete stealth browser MCP server for AI agents.**

84 tools. Undetectable by anti-bot systems. Full CDP access.\
LLM-ready markdown. Auto cookie consent dismiss (100+ CMPs).\
Accessibility snapshots, PDF export, HAR capture, network hooks, element cloning.

[![MCP](https://img.shields.io/badge/MCP-Compatible-F77F00?style=flat-square)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-F77F00?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-F77F00?style=flat-square)](https://python.org)
[![Tools](https://img.shields.io/badge/Tools-84-F77F00?style=flat-square)](#tools-reference)

</div>

---

## What is this?

An MCP server that gives AI agents (Claude, Cursor, Windsurf, etc.) a fully undetectable browser with 84 automation tools. Built on [nodriver](https://github.com/ultrafunkamsterdam/nodriver) + Chrome DevTools Protocol + [FastMCP](https://github.com/jlowin/fastmcp).

**Why not Playwright MCP?** Playwright is detectable. Sites with Cloudflare, DataDome, or any anti-bot system will block it. ScrapeLab uses nodriver (the successor of undetected-chromedriver) — no `navigator.webdriver` flag, no automation fingerprints, no detection.

### Key differentiators

| Feature | ScrapeLab MCP | [Playwright MCP](https://github.com/microsoft/playwright-mcp) | [Stealth Browser MCP](https://github.com/vibheksoni/stealth-browser-mcp) |
|---------|:---:|:---:|:---:|
| Anti-bot bypass (Cloudflare, DataDome) | Yes | No | Yes |
| Markdown output (LLM-ready) | Yes | Yes | No |
| Cookie consent auto-dismiss (100+ CMPs) | Yes | No | No |
| Accessibility snapshots | Yes | Yes | No |
| PDF export | Yes | Yes | No |
| HAR export | Yes | No | No |
| Network interception + hooks | Deep (Python hooks) | Routes only | Deep |
| Element cloning (styles, events, animations) | Full CDP | No | Full CDP |
| Progressive element cloning | Yes | No | Yes |
| Tools | 84 | 61 | 90 |
| Modular sections (enable/disable) | Yes | Capabilities | Yes |

---

## LLM-Ready Markdown

`get_page_content` returns clean markdown instead of raw HTML — 98-99% smaller, ready for LLM consumption.

| Mode | Engine | Best for | Size reduction |
|------|--------|----------|:-:|
| `readability=False` (default) | html2text | Full page structure, navigation, all content | ~98% |
| `readability=True` | trafilatura | Article/main content only, precision extraction | ~99% |

Both modes strip scripts, styles, SVGs, cookie banners, navigation chrome, and HTML comments before conversion.

## Cookie Consent Auto-Dismiss

Every `navigate` call automatically dismisses cookie/GDPR consent popups. No manual clicks, no leftover overlays blocking your scraper.

**Three-layer system:**

1. **[DuckDuckGo autoconsent](https://github.com/duckduckgo/autoconsent)** — 2863 rules covering 100+ consent management platforms (iubenda, Cookiebot, OneTrust, Quantcast, TrustArc, etc.)
2. **CMP JS API fallback** — Calls platform APIs directly from the main page (`_sp_.destroyMessages()`, `OneTrust.AllowAll()`, `__tcfapi`, Didomi, Cookiebot) — handles cross-origin iframe popups like SourcePoint
3. **DOM click fallback** — Catches multi-step consent flows (e.g. iubenda's 2-click Italian flow) by re-clicking accept buttons

Disable per-instance with `spawn_browser(auto_dismiss_consent=False)`.

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/competitorch/ScrapeLabMCP.git
cd ScrapeLabMCP
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add to your MCP client

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "scrapelab-mcp": {
      "command": "/path/to/ScrapeLabMCP/.venv/bin/python",
      "args": ["/path/to/ScrapeLabMCP/src/server.py"]
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

### 3. Use it

```
You: "Open a browser and navigate to example.com"
You: "Take a screenshot and get the accessibility snapshot"
You: "Get the page content as markdown"
You: "Export the page as PDF"
You: "Show me all network requests and export as HAR"
```

---

## Tools Reference (84 tools)

### Browser Management (10 tools)

| Tool | Description |
|------|-------------|
| `spawn_browser` | Launch undetectable browser instance (headless, proxy, custom UA, auto-consent) |
| `navigate` | Navigate to URL with wait conditions + auto cookie consent dismiss |
| `close_instance` | Clean shutdown of browser instance |
| `list_instances` | List all active browser instances |
| `get_instance_state` | Full page state (URL, cookies, storage, viewport) |
| `go_back` / `go_forward` | Browser history navigation |
| `reload_page` | Reload with optional cache bypass |
| `get_accessibility_snapshot` | Structured accessibility tree — the fastest way for an LLM to understand a page |
| `save_as_pdf` | Export page as PDF with full layout control |

### Element Interaction (11 tools)

| Tool | Description |
|------|-------------|
| `query_elements` | Find elements by CSS/XPath with visibility info |
| `click_element` | Natural click with fallback strategies |
| `type_text` | Human-like typing |
| `paste_text` | Instant paste via CDP |
| `scroll_page` | Directional scrolling |
| `wait_for_element` | Smart wait with timeout |
| `execute_script` | Run JavaScript in page context |
| `select_option` | Dropdown selection |
| `get_element_state` | Element properties and bounding box |
| `take_screenshot` | Screenshot (viewport, full page, or element) |
| `get_page_content` | HTML, text, or markdown (`readability=True` for article extraction) |

### Element Extraction (8 tools)

Deep extraction with optional `save_to_file=True` on every tool.\
Style extraction supports `method="js"` or `method="cdp"` for maximum accuracy.

| Tool | Description |
|------|-------------|
| `extract_element_styles` | 300+ CSS properties, pseudo-elements, inheritance chain |
| `extract_element_structure` | DOM tree, attributes, data attributes, children |
| `extract_element_events` | Event listeners, inline handlers, framework detection |
| `extract_element_animations` | CSS animations, transitions, transforms, keyframes |
| `extract_element_assets` | Images, backgrounds, fonts, icons, videos |
| `extract_related_files` | Linked CSS/JS files, imports, modules |
| `clone_element_complete` | Master clone: all of the above in one call (`method="comprehensive"` or `"cdp"`) |

### Progressive Cloning (10 tools)

Lazy-load element data on demand — start lightweight, expand what you need.

| Tool | Description |
|------|-------------|
| `clone_element_progressive` | Base structure with `element_id` for on-demand expansion |
| `expand_styles` / `expand_events` / `expand_children` | Expand specific data categories |
| `expand_css_rules` / `expand_pseudo_elements` / `expand_animations` | Expand detailed styling data |
| `list_stored_elements` / `clear_stored_element` / `clear_all_elements` | Manage stored elements |

### Network & Traffic (12 tools)

Deep network monitoring with interception, search, and standard export formats.

| Tool | Description |
|------|-------------|
| `list_network_requests` | All captured requests with type filtering |
| `get_request_details` / `get_response_details` / `get_response_content` | Inspect individual requests |
| `search_network_requests` | Search by URL pattern, method, status, body content |
| `modify_headers` | Modify request headers for future requests |
| `set_network_capture_filters` / `get_network_capture_filters` | Control what gets captured |
| `export_network_data` / `import_network_data` | JSON export/import |
| `export_har` | Export as HAR 1.2 — importable in Chrome DevTools, Postman, Fiddler |

### Dynamic Hooks (7 tools)

AI-generated Python functions that intercept and modify network traffic in real-time.

| Tool | Description |
|------|-------------|
| `create_dynamic_hook` | Full hook with custom Python function |
| `create_simple_dynamic_hook` | Template hook (block, redirect, add_headers, log) |
| `list_dynamic_hooks` / `get_dynamic_hook_details` / `remove_dynamic_hook` | Manage hooks |
| `get_hook_documentation` | Docs for writing hooks (overview, requirements, examples, patterns) |
| `validate_hook_function` | Validate hook code before deploying |

### CDP Functions (12 tools)

Direct Chrome DevTools Protocol access for advanced automation.

| Tool | Description |
|------|-------------|
| `execute_cdp_command` | Raw CDP command execution |
| `discover_global_functions` / `discover_object_methods` | Discover page APIs |
| `call_javascript_function` / `execute_function_sequence` | Call JS functions |
| `inject_and_execute_script` | Inject and run scripts |
| `inspect_function_signature` | Inspect function signatures |
| `create_persistent_function` | Functions that survive navigation |
| `create_python_binding` / `execute_python_in_browser` | Python-in-browser via py2js |
| `get_execution_contexts` / `list_cdp_commands` / `get_function_executor_info` | CDP introspection |

### Cookies & Storage (3 tools)

| Tool | Description |
|------|-------------|
| `get_cookies` / `set_cookie` / `clear_cookies` | Cookie management |

### Tab Management (5 tools)

| Tool | Description |
|------|-------------|
| `new_tab` / `list_tabs` / `switch_tab` / `close_tab` / `get_active_tab` | Full tab lifecycle |

### Debugging (5 tools)

| Tool | Description |
|------|-------------|
| `get_debug_view` / `clear_debug_view` / `export_debug_logs` / `get_debug_lock_status` | Debug system |
| `validate_browser_environment_tool` | Diagnose platform and browser issues |

---

## Modular Architecture

Load only what you need:

```bash
# Full suite (84 tools)
python src/server.py

# Core only — browser + element interaction
python src/server.py --minimal

# Disable specific sections
python src/server.py --disable-cdp-functions --disable-progressive-cloning

# List all sections
python src/server.py --list-sections
```

### Sections

| Section | Tools | Description |
|---------|-------|-------------|
| `browser-management` | 10 | Core browser ops, accessibility, PDF |
| `element-interaction` | 11 | Click, type, scroll, screenshot, markdown |
| `element-extraction` | 8 | Deep element cloning with save_to_file |
| `network-debugging` | 12 | Network monitoring, HAR export |
| `cdp-functions` | 12 | Raw CDP access |
| `progressive-cloning` | 10 | Lazy element expansion |
| `cookies-storage` | 3 | Cookie management |
| `tabs` | 5 | Tab management |
| `debugging` | 5 | Debug tools |
| `dynamic-hooks` | 7 | Network hook system |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SCRAPELAB_IDLE_TIMEOUT` | `5` | Minutes before idle browser instances are auto-closed |
| `PORT` | `8000` | Port for HTTP/SSE transport |

---

## Troubleshooting

**No compatible browser found** — Install Chrome, Chromium, or Edge. Run `validate_browser_environment_tool()` to diagnose.

**Too many tools for your use case** — Use `--minimal` or `--disable-<section>`.

**Browser instances piling up** — Instances auto-close after 5 minutes of inactivity (configurable via `SCRAPELAB_IDLE_TIMEOUT`).

---

## License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

Built by [Edoardo Nardi](https://github.com/edoardo-nardi)\
Stealth engine powered by [nodriver](https://github.com/ultrafunkamsterdam/nodriver)

</div>
