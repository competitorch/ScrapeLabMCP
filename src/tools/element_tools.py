"""Element interaction tools: click, type, scroll, query, screenshot, etc."""

import asyncio
import base64
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def register(ctx):
    """Register element interaction tools."""

    @ctx.section_tool("element-interaction")
    async def query_elements(
        instance_id: str,
        selector: str,
        limit: int = 10,
        include_text: bool = True,
        include_attributes: bool = True,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Query DOM elements using CSS selectors.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector to query.
            limit (int): Maximum number of elements to return.
            include_text (bool): Include element text content.
            include_attributes (bool): Include element attributes.

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]]: List of matching elements, or file metadata if response too large.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        elements = await ctx.dom_handler.query_elements(
            tab, selector, limit, include_text, include_attributes
        )
        return ctx.response_handler.handle_response(elements, "query_elements")

    @ctx.section_tool("element-interaction")
    async def click_element(
        instance_id: str,
        selector: str,
        click_type: str = "click",
        button: str = "left",
    ) -> bool:
        """
        Click on an element.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.
            click_type (str): Type of click: 'click', 'double', 'right'.
            button (str): Mouse button: 'left', 'right', 'middle'.

        Returns:
            bool: True if clicked successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.click_element(tab, selector, click_type, button)

    @ctx.section_tool("element-interaction")
    async def type_text(
        instance_id: str,
        selector: str,
        text: str,
        delay: int = 50,
        clear_first: bool = True,
    ) -> bool:
        """
        Type text into an input element.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the input element.
            text (str): Text to type.
            delay (int): Delay between keystrokes in milliseconds.
            clear_first (bool): Clear existing text before typing.

        Returns:
            bool: True if typed successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.type_text(tab, selector, text, delay, clear_first)

    @ctx.section_tool("element-interaction")
    async def paste_text(
        instance_id: str,
        selector: str,
        text: str,
        clear_first: bool = True,
    ) -> bool:
        """
        Paste text into an input element instantly (no keystroke delay).

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the input element.
            text (str): Text to paste.
            clear_first (bool): Clear existing text before pasting.

        Returns:
            bool: True if pasted successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.paste_text(tab, selector, text, clear_first)

    @ctx.section_tool("element-interaction")
    async def select_option(
        instance_id: str,
        selector: str,
        value: Optional[str] = None,
        label: Optional[str] = None,
        index: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Select an option from a <select> element.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the select element.
            value (Optional[str]): Option value to select.
            label (Optional[str]): Option label text to select.
            index (Optional[int]): Option index to select.

        Returns:
            Dict[str, Any]: Selected option details.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.select_option(tab, selector, value, label, index)

    @ctx.section_tool("element-interaction")
    async def get_element_state(
        instance_id: str,
        selector: str,
    ) -> Dict[str, Any]:
        """
        Get the current state of an element (visibility, value, checked, etc.).

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector for the element.

        Returns:
            Dict[str, Any]: Element state information.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.get_element_state(tab, selector)

    @ctx.section_tool("element-interaction")
    async def wait_for_element(
        instance_id: str,
        selector: str,
        timeout: int = 30000,
        state: str = "visible",
    ) -> bool:
        """
        Wait for an element to reach a specific state.

        Args:
            instance_id (str): Browser instance ID.
            selector (str): CSS selector to wait for.
            timeout (int): Maximum wait time in milliseconds.
            state (str): Target state: 'visible', 'hidden', 'attached', 'detached'.

        Returns:
            bool: True if element reached the target state.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.wait_for_element(tab, selector, timeout, state)

    @ctx.section_tool("element-interaction")
    async def scroll_page(
        instance_id: str,
        direction: str = "down",
        amount: int = 500,
        selector: Optional[str] = None,
    ) -> bool:
        """
        Scroll the page or a specific element.

        Args:
            instance_id (str): Browser instance ID.
            direction (str): Scroll direction: 'up', 'down', 'left', 'right'.
            amount (int): Scroll amount in pixels.
            selector (Optional[str]): Optional element selector to scroll within.

        Returns:
            bool: True if scrolled successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.scroll(tab, direction, amount, selector)

    @ctx.section_tool("element-interaction")
    async def execute_script(
        instance_id: str,
        script: str,
        args: Optional[List[Any]] = None,
    ) -> Any:
        """
        Execute JavaScript in the page context.

        Args:
            instance_id (str): Browser instance ID.
            script (str): JavaScript code to execute.
            args (Optional[List[Any]]): Arguments to pass to the script.

        Returns:
            Any: Script execution result.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.execute_script(tab, script, args)

    @ctx.section_tool("element-interaction")
    async def get_page_content(
        instance_id: str,
        content_type: str = "html",
        readability: bool = False,
    ) -> Dict[str, Any]:
        """
        Get page content in various formats.

        Args:
            instance_id (str): Browser instance ID.
            content_type (str): Type of content: 'html', 'text', 'markdown'.
            readability (bool): Extract main article content only via Mozilla Readability. Use with content_type='markdown' for clean, LLM-ready output.

        Returns:
            Dict[str, Any]: Page content in the requested format with url and title.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.dom_handler.get_page_content(tab, content_type=content_type, readability=readability)

    @ctx.section_tool("element-interaction")
    async def take_screenshot(
        instance_id: str,
        selector: Optional[str] = None,
        full_page: bool = False,
        quality: int = 80,
    ) -> Union[str, Dict[str, Any]]:
        """
        Take a screenshot of the page or a specific element.

        Args:
            instance_id (str): Browser instance ID.
            selector (Optional[str]): CSS selector for element screenshot.
            full_page (bool): Capture full page screenshot.
            quality (int): JPEG quality (1-100).

        Returns:
            Union[str, Dict[str, Any]]: Base64-encoded screenshot or file metadata if too large.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")

        tmp_path = Path(tempfile.mktemp(suffix=".png"))
        try:
            if selector:
                element = await tab.query_selector(selector)
                if not element:
                    raise Exception(f"Element not found: {selector}")
                await element.save_screenshot(str(tmp_path))
            elif full_page:
                await tab.save_screenshot(str(tmp_path), full_page=True)
            else:
                await tab.save_screenshot(str(tmp_path))

            raw_bytes = tmp_path.read_bytes()
            file_size_kb = len(raw_bytes) / 1024
            estimated_tokens = int(file_size_kb * 1.37 * 100)

            # Compress if needed
            try:
                from PIL import Image
                import io

                img = Image.open(io.BytesIO(raw_bytes))
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=quality)
                compressed_bytes = buf.getvalue()
            except ImportError:
                compressed_bytes = raw_bytes

            file_size_kb = len(compressed_bytes) / 1024
            estimated_tokens = int(file_size_kb * 1.37 * 100)

            if estimated_tokens > 20000:
                screenshot_dir = Path(tempfile.gettempdir()) / "scrapelab_screenshots"
                screenshot_dir.mkdir(exist_ok=True)
                from datetime import datetime

                screenshot_filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                screenshot_path = screenshot_dir / screenshot_filename
                screenshot_path.write_bytes(compressed_bytes)
                return {
                    "file_path": str(screenshot_path),
                    "filename": screenshot_filename,
                    "file_size_kb": round(file_size_kb, 2),
                    "estimated_tokens": estimated_tokens,
                    "reason": "Screenshot too large, automatically saved to file",
                    "message": f"Screenshot saved. AI agents should use the Read tool to view this image: {str(screenshot_path)}",
                }

            return base64.b64encode(compressed_bytes).decode("utf-8")

        finally:
            if tmp_path.exists():
                os.unlink(tmp_path)
