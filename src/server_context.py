"""Shared server context holding all dependencies for tool modules."""

from dataclasses import dataclass, field
from typing import Set, Callable

from fastmcp import FastMCP

from browser_manager import BrowserManager
from cdp_function_executor import CDPFunctionExecutor
from dom_handler import DOMHandler
from network_interceptor import NetworkInterceptor
from response_handler import response_handler
from debug_logger import debug_logger
from element_cloner import element_cloner
from comprehensive_element_cloner import comprehensive_element_cloner
from file_based_element_cloner import file_based_element_cloner
from progressive_element_cloner import progressive_element_cloner
from cdp_element_cloner import CDPElementCloner
from dynamic_hook_system import dynamic_hook_system
from dynamic_hook_ai_interface import dynamic_hook_ai
from persistent_storage import persistent_storage


@dataclass
class ServerContext:
    """Holds all shared state and dependencies for tool registration."""

    mcp: FastMCP
    disabled_sections: Set[str] = field(default_factory=set)

    # Core managers (created once, shared across all tools)
    browser_manager: BrowserManager = field(default_factory=BrowserManager)
    network_interceptor: NetworkInterceptor = field(default_factory=NetworkInterceptor)
    dom_handler: DOMHandler = field(default_factory=DOMHandler)
    cdp_function_executor: CDPFunctionExecutor = field(default_factory=CDPFunctionExecutor)

    # Singleton references (module-level instances)
    response_handler: object = field(default=None)
    debug_logger: object = field(default=None)
    element_cloner: object = field(default=None)
    comprehensive_element_cloner: object = field(default=None)
    file_based_element_cloner: object = field(default=None)
    progressive_element_cloner: object = field(default=None)
    dynamic_hook_ai: object = field(default=None)
    persistent_storage: object = field(default=None)

    def __post_init__(self):
        # Wire up module-level singletons
        self.response_handler = response_handler
        self.debug_logger = debug_logger
        self.element_cloner = element_cloner
        self.comprehensive_element_cloner = comprehensive_element_cloner
        self.file_based_element_cloner = file_based_element_cloner
        self.progressive_element_cloner = progressive_element_cloner
        self.dynamic_hook_ai = dynamic_hook_ai
        self.persistent_storage = persistent_storage

    def is_section_enabled(self, section: str) -> bool:
        """Check if a tool section is enabled."""
        return section not in self.disabled_sections

    def section_tool(self, section: str) -> Callable:
        """Decorator to conditionally register tools based on section status."""
        def decorator(func):
            if self.is_section_enabled(section):
                return self.mcp.tool(func)
            return func
        return decorator
