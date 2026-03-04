"""Network debugging tools: request listing, search, export, headers, HAR."""

import base64
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def register(ctx):
    """Register network debugging tools."""

    @ctx.section_tool("network-debugging")
    async def list_network_requests(
        instance_id: str,
        filter_type: Optional[str] = None,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List captured network requests.

        Args:
            instance_id (str): Browser instance ID.
            filter_type (Optional[str]): Filter by resource type (e.g., 'image', 'script', 'xhr').

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]]: List of network requests, or file metadata if response too large.
        """
        requests = await ctx.network_interceptor.list_requests(instance_id, filter_type)
        formatted_requests = [
            {
                "request_id": req.request_id,
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type,
                "timestamp": req.timestamp.isoformat(),
            }
            for req in requests
        ]
        return ctx.response_handler.handle_response(formatted_requests, "network_requests")

    @ctx.section_tool("network-debugging")
    async def get_request_details(request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a network request.

        Args:
            request_id (str): Network request ID.

        Returns:
            Optional[Dict[str, Any]]: Request details including headers, cookies, and body.
        """
        request = await ctx.network_interceptor.get_request(request_id)
        if request:
            return request.dict()
        return None

    @ctx.section_tool("network-debugging")
    async def get_response_details(request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get response details for a network request.

        Args:
            request_id (str): Network request ID.

        Returns:
            Optional[Dict[str, Any]]: Response details including status, headers, and metadata.
        """
        response = await ctx.network_interceptor.get_response(request_id)
        if response:
            return response.dict()
        return None

    @ctx.section_tool("network-debugging")
    async def get_response_content(
        instance_id: str,
        request_id: str,
    ) -> Optional[str]:
        """
        Get response body content.

        Args:
            instance_id (str): Browser instance ID.
            request_id (str): Network request ID.

        Returns:
            Optional[str]: Response body as text (base64 encoded for binary).
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        body = await ctx.network_interceptor.get_response_body(tab, request_id)
        if body:
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return base64.b64encode(body).decode("utf-8")
        return None

    @ctx.section_tool("network-debugging")
    async def search_network_requests(
        instance_id: str,
        url_pattern: Optional[str] = None,
        method: Optional[str] = None,
        status_code: Optional[int] = None,
        response_contains: Optional[str] = None,
        payload_contains: Optional[str] = None,
        resource_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Search network requests with advanced filters and pagination.

        Args:
            instance_id (str): Browser instance ID.
            url_pattern (Optional[str]): Filter by URL pattern (substring match).
            method (Optional[str]): Filter by HTTP method.
            status_code (Optional[int]): Filter by response status code.
            response_contains (Optional[str]): Search in response body.
            payload_contains (Optional[str]): Search in request payload.
            resource_type (Optional[str]): Filter by resource type.
            limit (int): Max results per page.
            offset (int): Starting index for pagination.

        Returns:
            Dict[str, Any]: Paginated results with metadata.
        """
        return await ctx.network_interceptor.search_requests(
            instance_id,
            url_pattern,
            method,
            status_code,
            response_contains,
            payload_contains,
            resource_type,
            limit,
            offset,
        )

    @ctx.section_tool("network-debugging")
    async def export_network_data(instance_id: str, filepath: str) -> bool:
        """
        Export network data to JSON file.

        Args:
            instance_id (str): Browser instance ID.
            filepath (str): Path to save JSON file.

        Returns:
            bool: True if successful.
        """
        return await ctx.network_interceptor.export_to_json(instance_id, filepath)

    @ctx.section_tool("network-debugging")
    async def import_network_data(instance_id: str, filepath: str) -> bool:
        """
        Import network data from JSON file.

        Args:
            instance_id (str): Browser instance ID.
            filepath (str): Path to JSON file.

        Returns:
            bool: True if successful.
        """
        return await ctx.network_interceptor.import_from_json(instance_id, filepath)

    @ctx.section_tool("network-debugging")
    async def set_network_capture_filters(
        instance_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
    ) -> bool:
        """
        Set resource type filters for network capture to reduce memory usage.

        Args:
            instance_id (str): Browser instance ID.
            include_types (Optional[List[str]]): Only capture these types (e.g., ['XHR', 'Fetch', 'Document']).
            exclude_types (Optional[List[str]]): Exclude these types (e.g., ['Image', 'Stylesheet', 'Font', 'Script']).

        Common resource types: Document, Stylesheet, Image, Media, Font, Script, XHR, Fetch, WebSocket, Manifest, Other

        Returns:
            bool: True if successful.
        """
        await ctx.network_interceptor.set_capture_filters(instance_id, include_types, exclude_types)
        return True

    @ctx.section_tool("network-debugging")
    async def get_network_capture_filters(instance_id: str) -> Dict[str, List[str]]:
        """
        Get current network capture filters.

        Args:
            instance_id (str): Browser instance ID.

        Returns:
            Dict[str, List[str]]: Current filters with 'include' and 'exclude' lists.
        """
        return await ctx.network_interceptor.get_capture_filters(instance_id)

    @ctx.section_tool("network-debugging")
    async def modify_headers(instance_id: str, headers: Dict[str, str]) -> bool:
        """
        Modify request headers for future requests.

        Args:
            instance_id (str): Browser instance ID.
            headers (Dict[str, str]): Headers to add/modify.

        Returns:
            bool: True if modified successfully.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")
        return await ctx.network_interceptor.modify_headers(tab, headers)

    # ── A5: HAR Export ────────────────────────────────────────────────

    @ctx.section_tool("network-debugging")
    async def export_har(
        instance_id: str,
        include_bodies: bool = False,
    ) -> Dict[str, Any]:
        """
        Export captured network traffic as a HAR (HTTP Archive 1.2) file.

        HAR files can be imported into Chrome DevTools, Postman, Charles Proxy,
        Fiddler, and other network analysis tools.

        Args:
            instance_id (str): Browser instance ID.
            include_bodies (bool): Include response bodies (can be large). Default False.

        Returns:
            Dict[str, Any]: File path, entry count, and total size.
        """
        tab = await ctx.browser_manager.get_tab(instance_id)
        if not tab:
            raise Exception(f"Instance not found: {instance_id}")

        requests = await ctx.network_interceptor.list_requests(instance_id)
        page_url = await tab.evaluate("window.location.href")
        page_title = await tab.evaluate("document.title")

        # Build HAR 1.2 structure
        entries = []
        for req in requests:
            resp = await ctx.network_interceptor.get_response(req.request_id)

            # Request headers as HAR name/value pairs
            req_headers = [{"name": k, "value": v} for k, v in req.headers.items()]
            req_cookies = [{"name": k, "value": v} for k, v in req.cookies.items()]

            entry = {
                "startedDateTime": req.timestamp.isoformat() + "Z",
                "time": 0,
                "request": {
                    "method": req.method,
                    "url": req.url,
                    "httpVersion": "HTTP/1.1",
                    "cookies": req_cookies,
                    "headers": req_headers,
                    "queryString": [],
                    "headersSize": -1,
                    "bodySize": len(req.post_data) if req.post_data else 0,
                },
                "response": {
                    "status": 0,
                    "statusText": "",
                    "httpVersion": "HTTP/1.1",
                    "cookies": [],
                    "headers": [],
                    "content": {"size": 0, "mimeType": ""},
                    "redirectURL": "",
                    "headersSize": -1,
                    "bodySize": -1,
                },
                "cache": {},
                "timings": {"send": 0, "wait": 0, "receive": 0},
            }

            # Add post data if present
            if req.post_data:
                entry["request"]["postData"] = {
                    "mimeType": req.headers.get("content-type", ""),
                    "text": req.post_data,
                }

            # Fill response if available
            if resp:
                resp_headers = [{"name": k, "value": v} for k, v in resp.headers.items()]
                entry["response"]["status"] = resp.status
                entry["response"]["statusText"] = ""
                entry["response"]["headers"] = resp_headers
                entry["response"]["content"]["size"] = resp.content_length or 0
                entry["response"]["content"]["mimeType"] = resp.content_type or ""

                if include_bodies and resp.body:
                    try:
                        text = resp.body.decode("utf-8")
                        entry["response"]["content"]["text"] = text
                    except UnicodeDecodeError:
                        entry["response"]["content"]["text"] = base64.b64encode(resp.body).decode("utf-8")
                        entry["response"]["content"]["encoding"] = "base64"

            entries.append(entry)

        har = {
            "log": {
                "version": "1.2",
                "creator": {"name": "ScrapeLab MCP", "version": "2.0"},
                "pages": [
                    {
                        "startedDateTime": datetime.now().isoformat() + "Z",
                        "id": "page_1",
                        "title": page_title,
                        "pageTimings": {"onContentLoad": -1, "onLoad": -1},
                    }
                ],
                "entries": entries,
            }
        }

        # Save to file
        har_dir = Path(tempfile.gettempdir()) / "scrapelab_har"
        har_dir.mkdir(exist_ok=True)
        filename = f"traffic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.har"
        har_path = har_dir / filename
        har_path.write_text(json.dumps(har, indent=2), encoding="utf-8")

        return {
            "file_path": str(har_path),
            "filename": filename,
            "entries": len(entries),
            "file_size_kb": round(har_path.stat().st_size / 1024, 2),
            "url": page_url,
            "title": page_title,
            "note": "Import this .har file into Chrome DevTools (Network tab) or Postman for analysis.",
        }
