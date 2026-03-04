<div align="center">

<img src="media/scrapelab-logo.svg" alt="ScrapeLab MCP" width="200"/>

# ScrapeLab MCP

**Intelligent web scraping + stealth browser automation for MCP agents.**

Combines smart scraping intelligence (recipe system, HTTP fast-path, auto-escalation) with an undetectable stealth browser powered by [nodriver](https://github.com/ultrafunkamsterdam/nodriver) + Chrome DevTools Protocol + [FastMCP](https://github.com/jlowin/fastmcp).

[![MCP](https://img.shields.io/badge/MCP-Compatible-F77F00?style=flat-square)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-F77F00?style=flat-square)](LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-F77F00?style=flat-square)](CONTRIBUTING.md)

</div>

---

## How It Works

```
scrape_url("https://example.com/products")
│
├─ 1. Recipe DB check (shared JSON in repo)
│   └─ Found? Use saved strategy (level, wait_for, proxy)
│
├─ 2. HTTP fast-path (~0.1s)
│   └─ httpx + header rotation → quality check
│   └─ Pass? → HTML → Markdown → done
│
└─ 3. Stealth browser fallback (~3s)
    └─ nodriver → navigate → wait → extract → close
    └─ Bypasses Cloudflare, antibots, JS rendering
```

The AI agent decides **what** to extract from the markdown. Recipes only store **how** to scrape (strategy).

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/your-org/scrapelab-mcp.git
cd scrapelab-mcp
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Add to your MCP client

**Claude Code CLI:**

```bash
claude mcp add-json scrapelab-mcp '{
  "type": "stdio",
  "command": "/path/to/scrapelab-mcp/venv/bin/python",
  "args": ["/path/to/scrapelab-mcp/src/server.py"]
}'
```

<details>
<summary><strong>Claude Desktop / Cursor (JSON config)</strong></summary>

```json
{
  "mcpServers": {
    "scrapelab-mcp": {
      "command": "/path/to/scrapelab-mcp/venv/bin/python",
      "args": ["/path/to/scrapelab-mcp/src/server.py"],
      "env": {}
    }
  }
}
```

</details>

### 3. Test it

```
> "Scrape https://example.com and extract all product names and prices."
```

---

## Scraping Tools

| Tool | Description |
|------|-------------|
| `scrape_url` | Smart scrape: recipe check → HTTP → browser fallback → structured data |
| `discover_url` | Analyze a page before scraping (framework, JSON-LD, APIs) |
| `batch_scrape_urls` | Parallel scrape of multiple URLs (lightweight results) |
| `save_recipe` | Save a scraping strategy for a site |
| `delete_recipe` | Remove a recipe |
| `list_recipes` | List all recipes + available knowledge |
| `get_specialist_recipe` | Get specialist guide (api-rest, ecommerce, wordpress...) |
| `get_output_schema` | Get JSON schema (generic, travel, ecommerce) |

### Recipe System — Site Bundles

Each site gets its own folder under `src/data/sites/` with everything needed:

```
src/data/sites/
├── weroad/
│   ├── config.json       # scraping strategy (level, wait_for, proxy)
│   ├── prompt.md         # extraction instructions for the LLM
│   ├── script.py         # reusable scraping script (optional)
│   └── schema.json       # output schema (optional)
│
├── gadventures/
│   ├── config.json
│   ├── prompt.md
│   └── script.py
```

When `scrape_url` matches a recipe, it returns the prompt, script, and schema — so Claude can execute immediately without regenerating code.

```
save_recipe(
  site_pattern="weroad.it",
  site_name="WeRoad",
  scrape_level=1,
  prompt="# WeRoad\n\nExtract all tours with dates and prices...",
  script="import httpx\n\nasync def scrape(url): ...",
)
```

---

## Browser Automation Tools

98 tools across 12 sections for full stealth browser control.

<details>
<summary><strong>Browser Management</strong> — 11 tools</summary>

| Tool | Description |
|------|-------------|
| `spawn_browser` | Create undetectable browser instance |
| `navigate` | Navigate to URLs |
| `close_instance` | Clean shutdown |
| `list_instances` | Manage multiple sessions |
| `get_instance_state` | Full browser state |
| `go_back` / `go_forward` | History navigation |
| `reload_page` | Reload current page |
| `take_screenshot` | Capture screenshots |
| `get_page_content` | HTML and metadata |

</details>

<details>
<summary><strong>Element Interaction</strong> — 11 tools</summary>

| Tool | Description |
|------|-------------|
| `query_elements` | Find elements by CSS/XPath |
| `click_element` | Natural clicking |
| `type_text` | Human-like typing |
| `paste_text` | Instant pasting via CDP |
| `scroll_page` | Natural scrolling |
| `wait_for_element` | Smart waiting |
| `execute_script` | Run JavaScript |
| `select_option` | Dropdown selection |
| `get_element_state` | Element properties |

</details>

<details>
<summary><strong>Element Extraction</strong> — 9 tools (CDP-accurate)</summary>

| Tool | Description |
|------|-------------|
| `extract_complete_element_cdp` | Complete CDP-based element clone |
| `clone_element_complete` | Full element cloning |
| `extract_element_styles` | 300+ CSS properties |
| `extract_element_structure` | Full DOM tree |
| `extract_element_events` | React/Vue/framework listeners |
| `extract_element_animations` | CSS animations/transitions |
| `extract_element_assets` | Images, fonts, videos |
| `extract_related_files` | Related CSS/JS files |

</details>

<details>
<summary><strong>Network & Hooks</strong> — 15 tools</summary>

| Tool | Description |
|------|-------------|
| `list_network_requests` | Captured requests |
| `get_request_details` | Headers and payload |
| `get_response_content` | Response data |
| `modify_headers` | Custom headers |
| `create_dynamic_hook` | Python functions for real-time interception |
| `create_simple_dynamic_hook` | Quick hook presets |
| `list_dynamic_hooks` | Active hooks |

</details>

<details>
<summary><strong>CDP Functions</strong> — 13 tools</summary>

| Tool | Description |
|------|-------------|
| `execute_cdp_command` | Direct CDP commands |
| `discover_global_functions` | Find JS functions |
| `call_javascript_function` | Execute any function |
| `inject_and_execute_script` | Custom JS code |
| `create_persistent_function` | Functions that survive reloads |
| `execute_python_in_browser` | Python via py2js |

</details>

<details>
<summary><strong>Progressive Cloning</strong> — 10 tools</summary>

| Tool | Description |
|------|-------------|
| `clone_element_progressive` | Lightweight initial structure |
| `expand_styles` | On-demand styles |
| `expand_events` | On-demand events |
| `expand_children` | Progressive children |
| `expand_css_rules` | CSS rules data |
| `expand_pseudo_elements` | Pseudo-elements |
| `expand_animations` | Animations data |

</details>

---

## Modular Architecture

Run the full suite or strip it down. Disable what you don't need.

```bash
python src/server.py --minimal              # 22 core tools
python src/server.py --disable-scraping     # No scraping tools
python src/server.py --disable-cdp-functions --disable-dynamic-hooks
python src/server.py --list-sections        # See all sections
```

---

## Stealth vs Playwright

| Feature | ScrapeLab MCP | Playwright MCP |
|---------|--------------|----------------|
| Cloudflare / antibot | Bypasses | Commonly blocked |
| Smart scraping | Recipe system + auto-escalation | Manual only |
| HTTP fast-path | Built-in (~0.1s) | No |
| Shared recipes | JSON in repo | No |
| UI element cloning | CDP-accurate | Limited |
| Network interception | Dynamic Python hooks | Basic |
| Total tools | 98 (customizable) | ~20 |

---

## Troubleshooting

**No compatible browser found** — Install Chrome, Chromium, or Edge. Run `validate_browser_environment_tool()` to diagnose.

**Tools hang or return malformed JSON** — Pull the latest branch. Debug output was fixed to not corrupt MCP JSON-RPC.

**Too many tools** — Use `--minimal` or selectively disable sections.

**batch_scrape_urls too large** — Batch returns lightweight results (analysis + 2000 char preview). Use `scrape_url` individually for full markdown.

---

## License

MIT — see [LICENSE](LICENSE).
