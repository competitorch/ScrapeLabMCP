"""Main MCP server for browser automation — slim orchestrator.

All tool implementations live in src/tools/*.py modules.
This file handles: FastMCP setup, lifespan, resources, CLI parsing.
"""

import argparse
import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from debug_logger import debug_logger
from persistent_storage import persistent_storage
from process_cleanup import process_cleanup
from server_context import ServerContext
from tools import register_all

# ═══════════════════════════════════════════════════════════════════════
#  CLI ARGUMENT PARSING (must run before tool registration)
# ═══════════════════════════════════════════════════════════════════════

ALL_SECTIONS = [
    "browser-management",
    "element-interaction",
    "element-extraction",
    "network-debugging",
    "cdp-functions",
    "progressive-cloning",
    "cookies-storage",
    "tabs",
    "debugging",
    "dynamic-hooks",
]

SECTION_DESCRIPTIONS = {
    "browser-management": "Core browser operations, accessibility, PDF export",
    "element-interaction": "Page interaction and element manipulation",
    "element-extraction": "Element cloning and extraction (supports save_to_file)",
    "network-debugging": "Network monitoring, interception, and HAR export",
    "cdp-functions": "Chrome DevTools Protocol function execution",
    "progressive-cloning": "Advanced element cloning system",
    "cookies-storage": "Cookie and storage management",
    "tabs": "Tab management",
    "debugging": "Debug and system tools",
    "dynamic-hooks": "AI-powered network hook system",
}


def _parse_args():
    """Parse CLI arguments and return (args, disabled_sections)."""
    parser = argparse.ArgumentParser(description="Stealth Browser MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse"],
        default="stdio",
        help="Transport protocol to use",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("PORT", 8000)),
        help="Port for HTTP transport",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host for HTTP transport")
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Enable only core browser management and element interaction",
    )
    parser.add_argument(
        "--list-sections",
        action="store_true",
        help="List all available tool sections and exit",
    )

    for section in ALL_SECTIONS:
        flag = f"--disable-{section}"
        parser.add_argument(flag, action="store_true", help=f"Disable {SECTION_DESCRIPTIONS[section]} tools")

    args = parser.parse_args()

    if args.list_sections:
        print("Available tool sections:")
        for section in ALL_SECTIONS:
            print(f"  {section}: {SECTION_DESCRIPTIONS[section]}")
        print("\nUse --disable-<section-name> to disable specific sections")
        print("Use --minimal to enable only core functionality")
        sys.exit(0)

    disabled = set()
    if args.minimal:
        disabled.update([
            "element-extraction", "network-debugging",
            "cdp-functions", "progressive-cloning", "cookies-storage",
            "tabs", "debugging", "dynamic-hooks",
        ])

    for section in ALL_SECTIONS:
        attr = f"disable_{section.replace('-', '_')}"
        if getattr(args, attr, False):
            disabled.add(section)

    return args, disabled


# Parse args at import time so section_tool decorators know what's disabled
_args, _disabled_sections = _parse_args()

if _disabled_sections:
    print(f"Disabled tool sections: {', '.join(sorted(_disabled_sections))}", file=sys.stderr)


# ═══════════════════════════════════════════════════════════════════════
#  LIFESPAN
# ═══════════════════════════════════════════════════════════════════════

IDLE_TIMEOUT_MINUTES = int(os.getenv("SCRAPELAB_IDLE_TIMEOUT", "5"))
IDLE_CHECK_INTERVAL = 60  # seconds between checks


async def _idle_cleanup_loop(context):
    """Background task: auto-close idle browser instances every IDLE_CHECK_INTERVAL seconds."""
    while True:
        await asyncio.sleep(IDLE_CHECK_INTERVAL)
        try:
            closed = await context.browser_manager.cleanup_inactive(IDLE_TIMEOUT_MINUTES)
            for instance_id in closed:
                await context.network_interceptor.clear_instance_data(instance_id)
                debug_logger.log_info(
                    "server", "idle_cleanup",
                    f"Auto-closed idle instance {instance_id} (timeout={IDLE_TIMEOUT_MINUTES}m)"
                )
        except Exception as e:
            debug_logger.log_error("server", "idle_cleanup", e)


@asynccontextmanager
async def app_lifespan(server):
    """Manage application lifecycle with proper cleanup."""
    debug_logger.log_info("server", "startup", "Starting Browser Automation MCP Server...")
    debug_logger.log_info("server", "startup", f"Idle auto-close timeout: {IDLE_TIMEOUT_MINUTES} minutes")

    # Start background idle-cleanup task
    cleanup_task = asyncio.create_task(_idle_cleanup_loop(ctx))

    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
        debug_logger.log_info("server", "shutdown", "Shutting down Browser Automation MCP Server...")

        try:
            await ctx.browser_manager.close_all()
            debug_logger.log_info("server", "cleanup", "All browser instances closed")
        except Exception as e:
            debug_logger.log_error("server", "cleanup", e)

        try:
            process_cleanup._cleanup_all_tracked()
            debug_logger.log_info("server", "cleanup", "Process cleanup complete")
        except Exception as e:
            debug_logger.log_error("server", "cleanup", f"Process cleanup failed: {e}")

        try:
            persistent_instances = persistent_storage.list_instances()
            if persistent_instances.get("instances"):
                debug_logger.log_info(
                    "server",
                    "storage_cleanup",
                    f"Clearing in-memory storage with {len(persistent_instances['instances'])} instances...",
                )
                persistent_storage.clear_all()
                debug_logger.log_info("server", "storage_cleanup", "In-memory storage cleared")
        except Exception as e:
            debug_logger.log_error("server", "storage_cleanup", e)

        debug_logger.log_info("server", "shutdown", "Browser Automation MCP Server shutdown complete")


# ═══════════════════════════════════════════════════════════════════════
#  MCP INSTANCE + CONTEXT + TOOL REGISTRATION
# ═══════════════════════════════════════════════════════════════════════

mcp = FastMCP(
    name="Browser Automation MCP",
    instructions="""
    This MCP server provides undetectable browser automation using nodriver (CDP-based).

    Key features:
    - Spawn and manage multiple browser instances
    - Navigate and interact with web pages
    - Query and manipulate DOM elements
    - Intercept and analyze network traffic
    - Execute JavaScript in page context
    - Manage cookies and storage

    All browser instances are undetectable by anti-bot systems.
    """,
    lifespan=app_lifespan,
)

ctx = ServerContext(mcp=mcp, disabled_sections=_disabled_sections)

# Register all tool modules
register_all(ctx)


# ═══════════════════════════════════════════════════════════════════════
#  MCP RESOURCES
# ═══════════════════════════════════════════════════════════════════════

@mcp.resource("browser://{instance_id}/state")
async def get_browser_state_resource(instance_id: str) -> str:
    """Get current state of a browser instance."""
    state = await ctx.browser_manager.get_page_state(instance_id)
    if state:
        return json.dumps(state.dict(), indent=2)
    return json.dumps({"error": "Instance not found"})


@mcp.resource("browser://{instance_id}/cookies")
async def get_cookies_resource(instance_id: str) -> str:
    """Get cookies for a browser instance."""
    tab = await ctx.browser_manager.get_tab(instance_id)
    if tab:
        cookies = await ctx.network_interceptor.get_cookies(tab)
        return json.dumps(cookies, indent=2)
    return json.dumps({"error": "Instance not found"})


@mcp.resource("browser://{instance_id}/network")
async def get_network_resource(instance_id: str) -> str:
    """Get network requests for a browser instance."""
    requests = await ctx.network_interceptor.list_requests(instance_id)
    return json.dumps([req.dict() for req in requests], indent=2)


@mcp.resource("browser://{instance_id}/console")
async def get_console_resource(instance_id: str) -> str:
    """Get console logs for a browser instance."""
    state = await ctx.browser_manager.get_page_state(instance_id)
    if state:
        return json.dumps(state.console_logs, indent=2)
    return json.dumps({"error": "Instance not found"})


# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def main():
    """Entry point for uvx / pyproject.toml [project.scripts]."""
    if _args.transport == "http":
        mcp.run(transport="http", host=_args.host, port=_args.port)
    elif _args.transport == "sse":
        mcp.run(transport="sse", host=_args.host, port=_args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
