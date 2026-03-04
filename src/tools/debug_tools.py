"""Debug and system tools: debug view, hot reload, environment validation."""

import asyncio
import importlib
import sys
from typing import Any, Dict

from platform_utils import validate_browser_environment, get_platform_info


def register(ctx):
    """Register debug and system tools."""

    @ctx.section_tool("debugging")
    async def get_debug_view(
        max_errors: int = 50,
        max_warnings: int = 50,
        max_info: int = 50,
        include_all: bool = False,
    ) -> Dict[str, Any]:
        """
        Get comprehensive debug view with all logged errors and statistics.

        Args:
            max_errors (int): Maximum number of errors to include (default: 50).
            max_warnings (int): Maximum number of warnings to include (default: 50).
            max_info (int): Maximum number of info logs to include (default: 50).
            include_all (bool): Include all logs regardless of limits (default: False).

        Returns:
            Dict[str, Any]: Debug information including errors, warnings, and statistics.
        """
        return ctx.debug_logger.get_debug_view_paginated(
            max_errors=max_errors if not include_all else None,
            max_warnings=max_warnings if not include_all else None,
            max_info=max_info if not include_all else None,
        )

    @ctx.section_tool("debugging")
    async def clear_debug_view() -> bool:
        """
        Clear all debug logs and statistics with timeout protection.

        Returns:
            bool: True if cleared successfully.
        """
        try:
            await asyncio.wait_for(
                asyncio.to_thread(ctx.debug_logger.clear_debug_view_safe),
                timeout=10.0,
            )
            return True
        except asyncio.TimeoutError:
            return False

    @ctx.section_tool("debugging")
    async def export_debug_logs(
        filename: str = "debug_log.json",
        max_errors: int = 100,
        max_warnings: int = 100,
        max_info: int = 100,
        include_all: bool = False,
        format: str = "auto",
    ) -> str:
        """
        Export debug logs to a file using the fastest available method with timeout protection.

        Args:
            filename (str): Name of the file to export to.
            max_errors (int): Maximum number of errors to export (default: 100).
            max_warnings (int): Maximum number of warnings to export (default: 100).
            max_info (int): Maximum number of info logs to export (default: 100).
            include_all (bool): Include all logs regardless of limits (default: False).
            format (str): Export format: 'json', 'pickle', 'gzip-pickle', 'auto' (default: 'auto').

        Returns:
            str: Path to the exported file.
        """
        try:
            filepath = await asyncio.wait_for(
                asyncio.to_thread(
                    ctx.debug_logger.export_to_file_paginated,
                    filename,
                    max_errors if not include_all else None,
                    max_warnings if not include_all else None,
                    max_info if not include_all else None,
                    format,
                ),
                timeout=30.0,
            )
            return filepath
        except asyncio.TimeoutError:
            return "Export timeout - file too large. Try with smaller limits or 'gzip-pickle' format."

    @ctx.section_tool("debugging")
    async def get_debug_lock_status() -> Dict[str, Any]:
        """
        Get current debug logger lock status for debugging hanging exports.

        Returns:
            Dict[str, Any]: Lock status information.
        """
        try:
            return ctx.debug_logger.get_lock_status()
        except Exception as e:
            return {"error": str(e)}

    @ctx.section_tool("debugging")
    async def hot_reload() -> str:
        """
        Hot reload all modules without restarting the server.

        Returns:
            str: Status message.
        """
        try:
            from browser_manager import BrowserManager
            from network_interceptor import NetworkInterceptor
            from dom_handler import DOMHandler

            modules_to_reload = [
                "browser_manager",
                "network_interceptor",
                "dom_handler",
                "debug_logger",
                "models",
            ]
            reloaded_modules = []
            for module_name in modules_to_reload:
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                    reloaded_modules.append(module_name)
                    if module_name == "browser_manager":
                        ctx.browser_manager = BrowserManager()
                    elif module_name == "network_interceptor":
                        ctx.network_interceptor = NetworkInterceptor()
                    elif module_name == "dom_handler":
                        ctx.dom_handler = DOMHandler()
                    elif module_name == "debug_logger":
                        from debug_logger import debug_logger as dl
                        ctx.debug_logger = dl
            return f"Hot reload completed. Reloaded modules: {', '.join(reloaded_modules)}"
        except Exception as e:
            return f"Hot reload failed: {str(e)}"

    @ctx.section_tool("debugging")
    async def reload_status() -> str:
        """
        Check the status of loaded modules.

        Returns:
            str: Module status information.
        """
        try:
            modules_info = []
            modules_to_check = [
                "browser_manager",
                "network_interceptor",
                "dom_handler",
                "debug_logger",
                "models",
                "persistent_storage",
            ]
            for module_name in modules_to_check:
                if module_name in sys.modules:
                    module = sys.modules[module_name]
                    modules_info.append(
                        f"OK {module_name}: {getattr(module, '__file__', 'built-in')}"
                    )
                else:
                    modules_info.append(f"NOT LOADED {module_name}")
            return "\n".join(modules_info)
        except Exception as e:
            return f"Error checking module status: {str(e)}"

    @ctx.section_tool("debugging")
    async def validate_browser_environment_tool() -> Dict[str, Any]:
        """
        Validate browser environment and diagnose potential issues.

        Returns:
            Dict[str, Any]: Environment validation results with platform info and recommendations.
        """
        try:
            return validate_browser_environment()
        except Exception as e:
            return {
                "error": str(e),
                "platform_info": get_platform_info(),
                "is_ready": False,
                "issues": [f"Validation failed: {str(e)}"],
                "warnings": [],
            }
