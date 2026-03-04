"""Tool modules for ScrapeLab MCP Server.

Each module exposes a `register(ctx)` function that registers its tools on the FastMCP instance.
"""

from tools.browser_tools import register as register_browser
from tools.element_tools import register as register_element
from tools.network_tools import register as register_network
from tools.cookies_tools import register as register_cookies
from tools.tab_tools import register as register_tabs
from tools.debug_tools import register as register_debug
from tools.extraction_tools import register as register_extraction
from tools.cdp_tools import register as register_cdp
from tools.hook_tools import register as register_hooks


def register_all(ctx):
    """Register all tool modules on the server context."""
    register_browser(ctx)
    register_element(ctx)
    register_network(ctx)
    register_cookies(ctx)
    register_tabs(ctx)
    register_debug(ctx)
    register_extraction(ctx)
    register_cdp(ctx)
    register_hooks(ctx)
