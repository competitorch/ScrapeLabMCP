"""Browser management tools: spawn, navigate, close, list instances, accessibility, PDF."""

import asyncio
import base64
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import nodriver as uc

from models import BrowserOptions
from consent import get_consent_scripts

# Fallback: CMP JS APIs (for platforms like SourcePoint that expose main-page APIs
# controlling cross-origin iframes) + DOM button clicks (for multi-step consent).
_CONSENT_FALLBACK_JS = r"""(() => {
    const h = [];
    // CMP JS APIs — dismiss from main page even when popup is in a cross-origin iframe
    if (window._sp_ && window._sp_.destroyMessages) {
        try { window._sp_.destroyMessages(); h.push('sp'); } catch(e) {}
    }
    if (window.OneTrust) {
        try { window.OneTrust.AllowAll(); window.OneTrust.Close(); h.push('ot'); } catch(e) {}
    }
    if (window.Didomi) {
        try { window.Didomi.setUserAgreeToAll(); h.push('di'); } catch(e) {}
    }
    if (window.Cookiebot) {
        try { window.Cookiebot.submitCustomConsent(true,true,true); h.push('cb'); } catch(e) {}
    }
    if (window.__tcfapi) {
        try { window.__tcfapi('acceptAll', 2, ()=>{}); h.push('tcf'); } catch(e) {}
    }
    // DOM button click
    const kw = /accept|agree|accetta|accetto|\bok\b|got it|allow all/i;
    const skip = /reject|decline|refuse|do not|don.t|manage|settings|customize|rifiut|person|preferen|necessary|senza|without|ohne|sans|opzion|option/i;
    for (const el of document.querySelectorAll('button, a[role="button"], input[type="button"]')) {
        if (!el.offsetParent) continue;
        const txt = (el.textContent || '').trim();
        if (txt.length > 50 || skip.test(txt)) continue;
        if (kw.test(txt)) { el.click(); h.push('dom:'+txt.substring(0,20)); break; }
    }
    return h.length ? h.join('+') : false;
})()"""

_CONSENT_IFRAME_KEYWORDS = (
    "consent", "privacy", "cookie", "cmp", "gdpr", "sp_message",
    "sourcepoint", "onetrust", "cookiebot", "didomi", "quantcast",
)


async def _dismiss_consent_in_iframes(tab):
    """Click accept buttons inside cross-origin consent iframes via CDP isolated worlds."""
    try:
        tree = await tab.send(uc.cdp.page.get_frame_tree())
        if not tree or not tree.frame_tree:
            return

        def collect_frames(node):
            frames = []
            if hasattr(node, 'child_frames') and node.child_frames:
                for child in node.child_frames:
                    frames.append(child.frame)
                    frames.extend(collect_frames(child))
            return frames

        for frame in collect_frames(tree.frame_tree):
            url = (frame.url or "").lower()
            if not any(kw in url for kw in _CONSENT_IFRAME_KEYWORDS):
                continue
            try:
                world = await tab.send(uc.cdp.page.create_isolated_world(
                    frame_id=frame.id_, world_name="scrapelab_consent",
                ))
                result = await tab.send(uc.cdp.runtime.evaluate(
                    expression=_CONSENT_FALLBACK_JS, context_id=world,
                    return_by_value=True,
                ))
                if result and hasattr(result, 'value') and result.value:
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def register(ctx):
    """Register browser management tools."""

    @ctx.section_tool("browser-management")
    async def spawn_browser(
        headless: bool = False,
        user_agent: Optional[str] = None,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        proxy: Optional[str] = None,
        block_resources: List[str] = None,
        extra_headers: Dict[str, str] = None,
        user_data_dir: Optional[str] = None,
        sandbox: Optional[Any] = None,
        auto_dismiss_consent: bool = True,
    ) -> Dict[str, Any]:
        """
        Spawn a new browser instance.

        Args:
            headless (bool): Run in headless mode.
            user_agent (Optional[str]): Custom user agent string.
            viewport_width (int): Viewport width in pixels.
            viewport_height (int): Viewport height in pixels.
            proxy (Optional[str]): Proxy server URL.
            block_resources (List[str]): List of resource types to block.
            extra_headers (Dict[str, str]): Additional HTTP headers.
            user_data_dir (Optional[str]): Path to user data directory.
            sandbox (Optional[Any]): Enable browser sandbox. Accepts bool, string, int, or None for auto-detect.
            auto_dismiss_consent (bool): Auto-dismiss cookie/GDPR consent banners after navigation (default True).

        Returns:
            Dict[str, Any]: Instance information including instance_id.
        """
        try:
            from platform_utils import is_running_as_root, is_running_in_container

            if sandbox is None:
                sandbox = not (is_running_as_root() or is_running_in_container())
            elif isinstance(sandbox, str):
                sandbox = sandbox.lower() in ("true", "1", "yes", "on", "enabled")
            elif isinstance(sandbox, int):
                sandbox = bool(sandbox)
            elif not isinstance(sandbox, bool):
                sandbox = bool(sandbox)

            options = BrowserOptions(
                headless=headless,
                user_agent=user_agent,
                viewport_width=viewport_width,
                viewport_height=viewport_height,
                proxy=proxy,
                block_resources=block_resources or [],
                extra_headers=extra_headers or {},
                user_data_dir=user_data_dir,
                sandbox=sandbox,
                auto_dismiss_consent=auto_dismiss_consent,
            )
            instance = await ctx.browser_manager.spawn_browser(options)
            tab = await ctx.browser_manager.get_tab(instance.instance_id)
            if tab:
                await ctx.network_interceptor.setup_interception(
                    tab, instance.instance_id, block_resources
                )
            return {
                "instance_id": instance.instance_id,
                "state": instance.state,
                "headless": instance.headless,
                "viewport": instance.viewport,
            }
        except Exception as e:
            raise Exception(f"Failed to spawn browser: {str(e)}")

    @ctx.section_tool("browser-management")
    async def list_instances() -> List[Dict[str, Any]]:
        """
        List all active browser instances.

        Returns:
            List[Dict[str, Any]]: List of browser instances with their current state.
        """
        memory_instances = await ctx.browser_manager.list_instances()
        storage_instances = ctx.persistent_storage.list_instances()
        result = []
        for inst in memory_instances:
            result.append({
                "instance_id": inst.instance_id,
                "state": inst.state,
                "current_url": inst.current_url,
                "title": inst.title,
                "source": "active",
            })
        memory_ids = {inst.instance_id for inst in memory_instances}
        for instance_id, inst_data in storage_instances.get("instances", {}).items():
            if instance_id not in memory_ids:
                result.append({
                    "instance_id": inst_data["instance_id"],
                    "state": inst_data["state"] + " (stored)",
                    "current_url": inst_data["current_url"],
                    "title": inst_data["title"],
                    "source": "stored",
                })
        return result

    @ctx.section_tool("browser-management")
    async def close_instance(instance_id: str) -> bool:
        """
        Close a browser instance.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            bool: True if closed successfully.
        """
        success = await ctx.browser_manager.close_instance(instance_id)
        if success:
            await ctx.network_interceptor.clear_instance_data(instance_id)
        return success

    @ctx.section_tool("browser-management")
    async def get_instance_state(instance_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed state of a browser instance.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            Optional[Dict[str, Any]]: Complete state information.
        """
        state = await ctx.browser_manager.get_page_state(instance_id)
        if state:
            return state.dict()
        return None

    @ctx.section_tool("browser-management")
    async def navigate(
        instance_id: str,
        url: str,
        wait_until: str = "load",
        timeout: int = 30000,
        referrer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Navigate to a URL.

        Args:
            instance_id (str): Browser instance ID.
            url (str): URL to navigate to.
            wait_until (str): Wait condition - 'load', 'domcontentloaded', or 'networkidle'.
            timeout (int): Navigation timeout in milliseconds.
            referrer (Optional[str]): Referrer URL.

        Returns:
            Dict[str, Any]: Navigation result with final URL and title.
        """
        if isinstance(timeout, str):
            timeout = int(timeout)
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        try:
            if referrer:
                await tab.send(uc.cdp.network.set_extra_http_headers(
                    headers={"Referer": referrer}
                ))
            await tab.get(url)
            if wait_until == "domcontentloaded":
                await tab.wait(uc.cdp.page.DomContentEventFired)
            elif wait_until == "networkidle":
                await asyncio.sleep(2)
            else:
                await tab.wait(uc.cdp.page.LoadEventFired)

            # Auto-dismiss cookie consent banners via DuckDuckGo autoconsent (100+ CMPs)
            instance_data = await ctx.browser_manager.get_instance(instance_id)
            opts = instance_data.get('options') if instance_data else None
            should_dismiss = getattr(opts, 'auto_dismiss_consent', False) if opts else False
            if should_dismiss:
                # 1. Autoconsent engine (100+ CMPs in main page)
                try:
                    bootstrap_js, iife_js = get_consent_scripts()
                    await asyncio.sleep(1.0)
                    await tab.evaluate(bootstrap_js)
                    await tab.evaluate(f"void(0);{iife_js};void(0)")
                    await asyncio.sleep(2.5)
                except Exception:
                    pass
                # 2. Iframe fallback (cross-origin consent popups: SourcePoint, etc.)
                try:
                    await _dismiss_consent_in_iframes(tab)
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
                # 3. DOM click fallback (multi-step consent, e.g. iubenda 2-click)
                try:
                    for _ in range(2):
                        await tab.evaluate(_CONSENT_FALLBACK_JS)
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

            final_url = await tab.evaluate("window.location.href")
            title = await tab.evaluate("document.title")
            await ctx.browser_manager.update_instance_state(instance_id, final_url, title)
            return {
                "url": final_url,
                "title": title,
                "success": True,
            }
        except Exception as e:
            raise

    @ctx.section_tool("browser-management")
    async def go_back(instance_id: str) -> bool:
        """
        Navigate back in browser history.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            bool: True if navigated back successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        await tab.back()
        return True

    @ctx.section_tool("browser-management")
    async def go_forward(instance_id: str) -> bool:
        """
        Navigate forward in browser history.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            bool: True if navigated forward successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        await tab.forward()
        return True

    @ctx.section_tool("browser-management")
    async def reload_page(instance_id: str, ignore_cache: bool = False) -> bool:
        """
        Reload the current page.

        Args:
            instance_id (str): Browser instance ID.
            ignore_cache (bool): If True, bypass cache and reload from server.

        Returns:
            bool: True if reloaded successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        await tab.reload(ignore_cache=ignore_cache)
        return True

    # ── A1: Accessibility Snapshot ──────────────────────────────────────

    @ctx.section_tool("browser-management")
    async def get_accessibility_snapshot(
        instance_id: str,
        interesting_only: bool = True,
        max_depth: int = 8,
    ) -> Dict[str, Any]:
        """
        Get the accessibility tree of the current page as a structured snapshot.

        Returns a compact, LLM-friendly representation of the page content and structure
        derived from ARIA roles, semantic HTML, and element properties.
        This is the most efficient way for an AI to understand page content without screenshots.

        Args:
            instance_id (str): Browser instance ID.
            interesting_only (bool): If True, collapse generic wrappers for a cleaner tree.
            max_depth (int): Maximum tree depth (default 8).

        Returns:
            Dict[str, Any]: Accessibility snapshot with 'tree' (nested structure) and 'stats'.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")

        js_code = """
        ((maxDepth, interestingOnly) => {
            const ROLES = {
                'a': 'link', 'button': 'button', 'input': 'textbox', 'select': 'combobox',
                'textarea': 'textbox', 'img': 'img', 'nav': 'navigation', 'main': 'main',
                'header': 'banner', 'footer': 'contentinfo', 'aside': 'complementary',
                'h1': 'heading', 'h2': 'heading', 'h3': 'heading',
                'h4': 'heading', 'h5': 'heading', 'h6': 'heading',
                'ul': 'list', 'ol': 'list', 'li': 'listitem', 'table': 'table',
                'tr': 'row', 'th': 'columnheader', 'td': 'cell',
                'form': 'form', 'section': 'region', 'article': 'article',
                'dialog': 'dialog', 'details': 'group', 'summary': 'button',
            };
            let nodeCount = 0;

            function walk(el, depth) {
                if (depth > maxDepth) return null;
                nodeCount++;
                const tag = el.tagName ? el.tagName.toLowerCase() : '';
                const role = el.getAttribute('role') || ROLES[tag] || 'generic';
                const name = el.getAttribute('aria-label')
                    || el.getAttribute('alt')
                    || el.getAttribute('title')
                    || el.getAttribute('placeholder')
                    || (['A','BUTTON','LABEL','H1','H2','H3','H4','H5','H6','TH','TD','LI','OPTION']
                        .includes(el.tagName) ? el.textContent.trim().substring(0, 120) : '');

                const n = {role};
                if (name) n.name = name;
                if (el.value !== undefined && el.value !== '') n.value = String(el.value);
                if (el.href) n.href = el.href;
                if (el.type === 'checkbox' || el.type === 'radio') n.checked = el.checked;
                if (el.disabled) n.disabled = true;
                if (el.required) n.required = true;
                const level = el.getAttribute('aria-level') || ({'H1':'1','H2':'2','H3':'3','H4':'4','H5':'5','H6':'6'}[el.tagName]);
                if (level) n.level = parseInt(level);

                const kids = [];
                for (const child of el.children) {
                    try {
                        const style = window.getComputedStyle(child);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                    } catch(e) { continue; }
                    const c = walk(child, depth + 1);
                    if (!c) continue;
                    if (interestingOnly && c.role === 'generic' && !c.name && c.children && c.children.length === 1) {
                        kids.push(c.children[0]);
                    } else if (!interestingOnly || c.role !== 'generic' || c.name || (c.children && c.children.length > 0)) {
                        kids.push(c);
                    }
                }
                if (kids.length > 0) n.children = kids;
                return n;
            }

            const tree = walk(document.body, 0);
            return JSON.stringify({tree, nodeCount});
        })(""" + str(max_depth) + "," + ("true" if interesting_only else "false") + ")"

        raw = await tab.evaluate(js_code)
        import json as _json
        data = _json.loads(raw)

        url = await tab.evaluate("window.location.href")
        title = await tab.evaluate("document.title")

        return {
            "url": url,
            "title": title,
            "tree": data["tree"],
            "stats": {"total_nodes": data["nodeCount"]},
        }

    # ── A2: PDF Export ────────���─────────────────────────────────────────

    @ctx.section_tool("browser-management")
    async def save_as_pdf(
        instance_id: str,
        landscape: bool = False,
        print_background: bool = True,
        scale: float = 1.0,
        paper_width: float = 8.5,
        paper_height: float = 11.0,
        margin_top: float = 0.4,
        margin_bottom: float = 0.4,
        margin_left: float = 0.4,
        margin_right: float = 0.4,
        page_ranges: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Save the current page as a PDF file.

        Uses Chrome's built-in print-to-PDF via CDP. Works only in headless mode
        or when the page allows printing.

        Args:
            instance_id (str): Browser instance ID.
            landscape (bool): Print in landscape orientation.
            print_background (bool): Include background colors/images.
            scale (float): Scale factor (0.1 to 2.0).
            paper_width (float): Paper width in inches (default: 8.5 = US Letter).
            paper_height (float): Paper height in inches (default: 11 = US Letter).
            margin_top (float): Top margin in inches.
            margin_bottom (float): Bottom margin in inches.
            margin_left (float): Left margin in inches.
            margin_right (float): Right margin in inches.
            page_ranges (Optional[str]): Page ranges to print, e.g. '1-3, 5'.

        Returns:
            Dict[str, Any]: File path, size, and page info.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")

        result = await tab.send(uc.cdp.page.print_to_pdf(
            landscape=landscape,
            print_background=print_background,
            scale=scale,
            paper_width=paper_width,
            paper_height=paper_height,
            margin_top=margin_top,
            margin_bottom=margin_bottom,
            margin_left=margin_left,
            margin_right=margin_right,
            page_ranges=page_ranges,
            transfer_mode="ReturnAsBase64",
        ))

        # result is a tuple (data: str, stream: Optional[StreamHandle])
        pdf_b64 = result[0] if isinstance(result, tuple) else result
        pdf_bytes = base64.b64decode(pdf_b64)

        # Save to file
        pdf_dir = Path(tempfile.gettempdir()) / "scrapelab_pdfs"
        pdf_dir.mkdir(exist_ok=True)
        filename = f"page_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = pdf_dir / filename
        pdf_path.write_bytes(pdf_bytes)

        url = await tab.evaluate("window.location.href")
        title = await tab.evaluate("document.title")

        return {
            "file_path": str(pdf_path),
            "filename": filename,
            "file_size_kb": round(len(pdf_bytes) / 1024, 2),
            "url": url,
            "title": title,
            "settings": {
                "landscape": landscape,
                "paper": f"{paper_width}x{paper_height} inches",
                "scale": scale,
            },
        }
