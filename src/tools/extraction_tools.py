"""Element extraction tools: styles, structure, events, animations, assets, cloning.

Combines element-extraction and progressive-cloning sections.
All extraction tools support save_to_file=True to persist results to disk.
"""

import json
from typing import Any, Dict, List, Optional

from cdp_element_cloner import CDPElementCloner


def register(ctx):
    """Register all element extraction tools."""

    # ─── helpers ───────────────────────────────────────────────────────
    async def _get_tab(instance_id: str):
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return tab

    def _maybe_save(result: Dict[str, Any], extraction_type: str, save: bool):
        """If save_to_file is True, persist result and return file metadata."""
        if not save:
            return result
        return ctx.file_based_element_cloner._save_extraction(result, extraction_type)

    # ═══════════════════════════════════════════════════════════════════
    #  ELEMENT EXTRACTION
    # ═══════════════════════════════════════════════════════════════════

    @ctx.section_tool("element-extraction")
    async def extract_element_styles(
        instance_id: str,
        selector: str,
        method: str = "js",
        include_computed: bool = True,
        include_css_rules: bool = True,
        include_pseudo: bool = True,
        include_inheritance: bool = False,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract complete styling information from an element.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            method (str): Extraction method - 'js' (JavaScript) or 'cdp' (Chrome DevTools Protocol, more reliable).
            include_computed (bool): Include computed styles.
            include_css_rules (bool): Include matching CSS rules.
            include_pseudo (bool): Include pseudo-element styles.
            include_inheritance (bool): Include style inheritance chain.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Complete styling data (or file path + summary if save_to_file=True).
        """
        tab = await _get_tab(instance_id)
        if method == "cdp":
            result = await ctx.element_cloner.extract_element_styles_cdp(
                tab, selector=selector,
                include_computed=include_computed, include_css_rules=include_css_rules,
                include_pseudo=include_pseudo, include_inheritance=include_inheritance,
            )
        else:
            result = await ctx.element_cloner.extract_element_styles(
                tab, selector=selector,
                include_computed=include_computed, include_css_rules=include_css_rules,
                include_pseudo=include_pseudo, include_inheritance=include_inheritance,
            )
        return _maybe_save(result, "styles", save_to_file)

    @ctx.section_tool("element-extraction")
    async def extract_element_structure(
        instance_id: str,
        selector: str,
        include_children: bool = False,
        include_attributes: bool = True,
        include_data_attributes: bool = True,
        max_depth: int = 3,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract complete HTML structure and DOM information.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            include_children (bool): Include child elements.
            include_attributes (bool): Include all attributes.
            include_data_attributes (bool): Include data-* attributes specifically.
            max_depth (int): Maximum depth for children extraction.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: HTML structure, attributes, position, and children data.
        """
        tab = await _get_tab(instance_id)
        result = await ctx.element_cloner.extract_element_structure(
            tab, selector=selector,
            include_children=include_children, include_attributes=include_attributes,
            include_data_attributes=include_data_attributes, max_depth=max_depth,
        )
        return _maybe_save(result, "structure", save_to_file)

    @ctx.section_tool("element-extraction")
    async def extract_element_events(
        instance_id: str,
        selector: str,
        include_inline: bool = True,
        include_listeners: bool = True,
        include_framework: bool = True,
        analyze_handlers: bool = False,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract complete event listener and JavaScript handler information.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            include_inline (bool): Include inline event handlers.
            include_listeners (bool): Include addEventListener handlers.
            include_framework (bool): Include framework-specific handlers.
            analyze_handlers (bool): Analyze handler functions for full details.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Event listeners, inline handlers, framework handlers.
        """
        tab = await _get_tab(instance_id)
        result = await ctx.element_cloner.extract_element_events(
            tab, selector=selector,
            include_inline=include_inline, include_listeners=include_listeners,
            include_framework=include_framework, analyze_handlers=analyze_handlers,
        )
        return _maybe_save(result, "events", save_to_file)

    @ctx.section_tool("element-extraction")
    async def extract_element_animations(
        instance_id: str,
        selector: str,
        include_css_animations: bool = True,
        include_transitions: bool = True,
        include_transforms: bool = True,
        analyze_keyframes: bool = True,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract CSS animations, transitions, and transforms.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            include_css_animations (bool): Include CSS @keyframes animations.
            include_transitions (bool): Include CSS transitions.
            include_transforms (bool): Include CSS transforms.
            analyze_keyframes (bool): Analyze keyframe rules.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Animation, transition, transform, and keyframe data.
        """
        tab = await _get_tab(instance_id)
        result = await ctx.element_cloner.extract_element_animations(
            tab, selector=selector,
            include_css_animations=include_css_animations, include_transitions=include_transitions,
            include_transforms=include_transforms, analyze_keyframes=analyze_keyframes,
        )
        return _maybe_save(result, "animations", save_to_file)

    @ctx.section_tool("element-extraction")
    async def extract_element_assets(
        instance_id: str,
        selector: str,
        include_images: bool = True,
        include_backgrounds: bool = True,
        include_fonts: bool = True,
        fetch_external: bool = False,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract all assets related to an element (images, fonts, etc.).

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            include_images (bool): Include img src and related images.
            include_backgrounds (bool): Include background images.
            include_fonts (bool): Include font information.
            fetch_external (bool): Whether to fetch external assets.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Images, background images, fonts, icons, videos, audio assets.
        """
        tab = await _get_tab(instance_id)
        result = await ctx.element_cloner.extract_element_assets(
            tab, selector=selector,
            include_images=include_images, include_backgrounds=include_backgrounds,
            include_fonts=include_fonts, fetch_external=fetch_external,
        )
        if save_to_file:
            return _maybe_save(result, "assets", True)
        return await ctx.response_handler.handle_response(
            result, f"element_assets_{instance_id}_{selector.replace(' ', '_')}"
        )

    @ctx.section_tool("element-extraction")
    async def extract_related_files(
        instance_id: str,
        analyze_css: bool = True,
        analyze_js: bool = True,
        follow_imports: bool = False,
        max_depth: int = 2,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Discover and analyze related CSS/JS files for context.

        Args:
            instance_id (str): Browser instance ID.
            analyze_css (bool): Analyze linked CSS files.
            analyze_js (bool): Analyze linked JS files.
            follow_imports (bool): Follow @import and module imports.
            max_depth (int): Maximum depth for following imports.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Stylesheets, scripts, imports, modules, framework detection.
        """
        tab = await _get_tab(instance_id)
        result = await ctx.element_cloner.extract_related_files(
            tab, analyze_css=analyze_css, analyze_js=analyze_js,
            follow_imports=follow_imports, max_depth=max_depth,
        )
        if save_to_file:
            return _maybe_save(result, "related_files", True)
        return await ctx.response_handler.handle_response(result, f"related_files_{instance_id}")

    @ctx.section_tool("element-extraction")
    async def clone_element_complete(
        instance_id: str,
        selector: str,
        method: str = "comprehensive",
        include_children: bool = True,
        save_to_file: bool = False,
    ) -> Dict[str, Any]:
        """
        Extract ALL element data — the master cloning function.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            method (str): 'comprehensive' (full JS-based) or 'cdp' (native CDP, 100% accuracy).
            include_children (bool): Whether to include child elements.
            save_to_file (bool): Save full data to file, return file path + summary.

        Returns:
            Dict[str, Any]: Complete element clone with all data.
        """
        tab = await _get_tab(instance_id)

        if method == "cdp":
            result = await CDPElementCloner().extract_complete_element_cdp(
                tab, selector, include_children
            )
        else:
            result = await ctx.comprehensive_element_cloner.extract_complete_element(
                tab, selector=selector, include_children=include_children,
            )

        if save_to_file:
            return _maybe_save(result, "complete_clone", True)
        return ctx.response_handler.handle_response(
            result, fallback_filename_prefix="complete_clone",
            metadata={"selector": selector, "url": getattr(tab, "url", "unknown")},
        )

    # ═══════════════════════════════════════════════════════════════════
    #  PROGRESSIVE CLONING
    # ═══════════════════════════════════════════════════════════════════

    @ctx.section_tool("progressive-cloning")
    async def clone_element_progressive(
        instance_id: str,
        selector: str,
        include_children: bool = True,
    ) -> Dict[str, Any]:
        """
        Clone element progressively - returns lightweight base structure with element_id.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            include_children (bool): Whether to extract child elements.

        Returns:
            Dict[str, Any]: Base structure with element_id for progressive expansion.
        """
        tab = await _get_tab(instance_id)
        return await ctx.progressive_element_cloner.clone_element_progressive(
            tab, selector, include_children
        )

    @ctx.section_tool("progressive-cloning")
    async def expand_styles(
        element_id: str,
        categories: Optional[List[str]] = None,
        properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Expand styles data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().
            categories (Optional[List[str]]): Style categories to include.
            properties (Optional[List[str]]): Specific CSS property names.

        Returns:
            Dict[str, Any]: Filtered styles data.
        """
        return ctx.progressive_element_cloner.expand_styles(element_id, categories, properties)

    @ctx.section_tool("progressive-cloning")
    async def expand_events(
        element_id: str,
        event_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Expand event listeners data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().
            event_types (Optional[List[str]]): Event types to include.

        Returns:
            Dict[str, Any]: Filtered event listeners data.
        """
        return ctx.progressive_element_cloner.expand_events(element_id, event_types)

    @ctx.section_tool("progressive-cloning")
    async def expand_children(
        element_id: str,
        depth_range: Optional[List] = None,
        max_count: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Expand children data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().
            depth_range (Optional[List]): [min_depth, max_depth] range.
            max_count (Optional[Any]): Maximum number of children to return.

        Returns:
            Dict[str, Any]: Filtered children data.
        """
        if isinstance(max_count, str):
            try:
                max_count = int(max_count) if max_count else None
            except ValueError:
                return {"error": f"Invalid max_count value: {max_count}"}

        if isinstance(depth_range, list):
            try:
                depth_range = [int(x) if isinstance(x, str) else x for x in depth_range]
            except ValueError:
                return {"error": f"Invalid depth_range values: {depth_range}"}

        depth_tuple = tuple(depth_range) if depth_range else None
        result = ctx.progressive_element_cloner.expand_children(element_id, depth_tuple, max_count)
        return ctx.response_handler.handle_response(result, f"expand_children_{element_id}")

    @ctx.section_tool("progressive-cloning")
    async def expand_css_rules(
        element_id: str,
        source_types: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Expand CSS rules data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().
            source_types (Optional[List[str]]): CSS rule sources to include.

        Returns:
            Dict[str, Any]: Filtered CSS rules data.
        """
        return ctx.progressive_element_cloner.expand_css_rules(element_id, source_types)

    @ctx.section_tool("progressive-cloning")
    async def expand_pseudo_elements(element_id: str) -> Dict[str, Any]:
        """
        Expand pseudo-elements data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().

        Returns:
            Dict[str, Any]: Pseudo-elements data (::before, ::after, etc.).
        """
        return ctx.progressive_element_cloner.expand_pseudo_elements(element_id)

    @ctx.section_tool("progressive-cloning")
    async def expand_animations(element_id: str) -> Dict[str, Any]:
        """
        Expand animations and fonts data for a stored element.

        Args:
            element_id (str): Element ID from clone_element_progressive().

        Returns:
            Dict[str, Any]: Animations, transitions, and fonts data.
        """
        return ctx.progressive_element_cloner.expand_animations(element_id)

    @ctx.section_tool("progressive-cloning")
    async def list_stored_elements() -> Dict[str, Any]:
        """
        List all stored elements with their basic info.

        Returns:
            Dict[str, Any]: List of stored elements with metadata.
        """
        return ctx.progressive_element_cloner.list_stored_elements()

    @ctx.section_tool("progressive-cloning")
    async def clear_stored_element(element_id: str) -> Dict[str, Any]:
        """
        Clear a specific stored element.

        Args:
            element_id (str): Element ID to clear.

        Returns:
            Dict[str, Any]: Success/error message.
        """
        return ctx.progressive_element_cloner.clear_stored_element(element_id)

    @ctx.section_tool("progressive-cloning")
    async def clear_all_elements() -> Dict[str, Any]:
        """
        Clear all stored elements.

        Returns:
            Dict[str, Any]: Success message.
        """
        return ctx.progressive_element_cloner.clear_all_elements()
