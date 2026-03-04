"""Network interception and traffic monitoring using CDP."""

import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import nodriver as uc
from nodriver import Tab

from models import NetworkRequest, NetworkResponse


class NetworkInterceptor:
    """Intercepts and manages network traffic for browser instances."""

    MAX_BODY_SIZE = 5 * 1024 * 1024  # 5 MB - skip response bodies larger than this
    MAX_REQUESTS_PER_INSTANCE = 1000  # Evict oldest requests when exceeded
    BODY_FETCH_TIMEOUT = 3  # seconds
    # Content type prefixes for which we skip body capture (binary/large)
    SKIP_BODY_TYPES = frozenset({'image', 'font', 'video', 'audio'})

    def __init__(self):
        self._requests: Dict[str, NetworkRequest] = {}
        self._responses: Dict[str, NetworkResponse] = {}
        self._instance_requests: Dict[str, List[str]] = {}
        self._instance_filters: Dict[str, Dict[str, List[str]]] = {}
        self._instance_locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()  # Only for creating/removing per-instance structures

    def _get_instance_lock(self, instance_id: str) -> asyncio.Lock:
        """Get or create a per-instance lock."""
        if instance_id not in self._instance_locks:
            self._instance_locks[instance_id] = asyncio.Lock()
        return self._instance_locks[instance_id]

    async def setup_interception(self, tab: Tab, instance_id: str, block_resources: List[str] = None):
        """
        Set up network interception for a tab.

        tab: Tab - The browser tab to intercept.
        instance_id: str - The browser instance identifier.
        block_resources: List[str] - List of resource types or URL patterns to block.
        """
        try:
            await tab.send(uc.cdp.network.enable())

            if block_resources:
                url_patterns = []
                resource_patterns = {
                    'image': ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp', '*.svg', '*.bmp', '*.ico'],
                    'stylesheet': ['*.css'],
                    'font': ['*.woff', '*.woff2', '*.ttf', '*.otf', '*.eot'],
                    'script': ['*.js', '*.mjs'],
                    'media': ['*.mp4', '*.mp3', '*.wav', '*.avi', '*.webm']
                }
                for resource_type in block_resources:
                    if resource_type.lower() in resource_patterns:
                        url_patterns.extend(resource_patterns[resource_type.lower()])
                    else:
                        url_patterns.append(resource_type)

                if url_patterns:
                    await tab.send(uc.cdp.network.set_blocked_ur_ls(urls=url_patterns))

            tab.add_handler(
                uc.cdp.network.RequestWillBeSent,
                lambda event: asyncio.create_task(self._on_request(event, instance_id)),
            )
            tab.add_handler(
                uc.cdp.network.ResponseReceived,
                lambda event: asyncio.create_task(self._on_response(event, instance_id, tab)),
            )

            # Initialize per-instance structures under global lock
            async with self._global_lock:
                if instance_id not in self._instance_requests:
                    self._instance_requests[instance_id] = []
                self._instance_locks.setdefault(instance_id, asyncio.Lock())
        except Exception as e:
            raise Exception(f"Failed to setup network interception: {str(e)}")

    async def _on_request(self, event, instance_id: str):
        """Handle request event."""
        try:
            request_id = event.request_id
            request = event.request
            resource_type = event.type.value if hasattr(event, "type") else None

            lock = self._get_instance_lock(instance_id)
            async with lock:
                filters = self._instance_filters.get(instance_id, {})
                include = filters.get("include", [])
                exclude = filters.get("exclude", [])

                if include and resource_type and resource_type.lower() not in [t.lower() for t in include]:
                    return
                if exclude and resource_type and resource_type.lower() in [t.lower() for t in exclude]:
                    return

            cookies = {}
            if hasattr(request, "headers") and "Cookie" in request.headers:
                cookie_str = request.headers["Cookie"]
                for cookie in cookie_str.split("; "):
                    if "=" in cookie:
                        key, value = cookie.split("=", 1)
                        cookies[key] = value

            network_request = NetworkRequest(
                request_id=request_id,
                instance_id=instance_id,
                url=request.url,
                method=request.method,
                headers=dict(request.headers) if hasattr(request, "headers") else {},
                cookies=cookies,
                post_data=request.post_data if hasattr(request, "post_data") else None,
                resource_type=resource_type,
            )

            async with lock:
                self._requests[request_id] = network_request
                self._instance_requests[instance_id].append(request_id)

                # Evict oldest requests when over the limit
                while len(self._instance_requests[instance_id]) > self.MAX_REQUESTS_PER_INSTANCE:
                    oldest_id = self._instance_requests[instance_id].pop(0)
                    self._requests.pop(oldest_id, None)
                    self._responses.pop(oldest_id, None)
        except Exception:
            pass

    async def _on_response(self, event, instance_id: str, tab: Tab = None):
        """Handle response event with timeout and content-type filtering."""
        try:
            request_id = event.request_id
            response = event.response
            content_type = response.mime_type if hasattr(response, "mime_type") else None

            body = None
            should_fetch = tab is not None
            # Skip body fetch for binary content types
            if content_type and should_fetch:
                top_type = content_type.split('/')[0].lower()
                if top_type in self.SKIP_BODY_TYPES:
                    should_fetch = False

            if should_fetch:
                try:
                    result = await asyncio.wait_for(
                        tab.send(uc.cdp.network.get_response_body(request_id=request_id)),
                        timeout=self.BODY_FETCH_TIMEOUT,
                    )
                    if result:
                        body_str, base64_encoded = result
                        if base64_encoded:
                            decoded = base64.b64decode(body_str)
                        else:
                            decoded = body_str.encode("utf-8")
                        if len(decoded) <= self.MAX_BODY_SIZE:
                            body = decoded
                except (asyncio.TimeoutError, Exception):
                    pass

            network_response = NetworkResponse(
                request_id=request_id,
                status=response.status,
                headers=dict(response.headers) if hasattr(response, "headers") else {},
                content_type=content_type,
                body=body,
            )

            lock = self._get_instance_lock(instance_id)
            async with lock:
                self._responses[request_id] = network_response
        except Exception:
            pass

    async def set_capture_filters(
        self,
        instance_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None,
    ):
        """Set resource type filters for network capture."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            self._instance_filters[instance_id] = {
                "include": include_types or [],
                "exclude": exclude_types or [],
            }

    async def get_capture_filters(self, instance_id: str) -> Dict[str, List[str]]:
        """Get current capture filters."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            return self._instance_filters.get(instance_id, {"include": [], "exclude": []})

    async def search_requests(
        self,
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
        """Search requests with advanced filters and pagination."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            request_ids = self._instance_requests.get(instance_id, [])
            matches = []

            for req_id in request_ids:
                if req_id not in self._requests:
                    continue

                request = self._requests[req_id]
                response = self._responses.get(req_id)

                if url_pattern and url_pattern.lower() not in request.url.lower():
                    continue
                if method and request.method.upper() != method.upper():
                    continue
                if resource_type and (not request.resource_type or resource_type.lower() not in request.resource_type.lower()):
                    continue
                if status_code and (not response or response.status != status_code):
                    continue
                if payload_contains and (not request.post_data or payload_contains.lower() not in request.post_data.lower()):
                    continue
                if response_contains and response and response.body:
                    try:
                        body_str = response.body.decode('utf-8', errors='ignore')
                        if response_contains.lower() not in body_str.lower():
                            continue
                    except:
                        continue

                matches.append({
                    "request_id": req_id,
                    "url": request.url,
                    "method": request.method,
                    "status": response.status if response else None,
                    "resource_type": request.resource_type,
                })

            total = len(matches)
            paginated = matches[offset:offset + limit]

            return {
                "results": paginated,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + limit < total,
            }

    async def list_requests(self, instance_id: str, filter_type: Optional[str] = None) -> List[NetworkRequest]:
        """List all requests for an instance."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            request_ids = self._instance_requests.get(instance_id, [])
            requests = []
            for req_id in request_ids:
                if req_id in self._requests:
                    request = self._requests[req_id]
                    if filter_type:
                        if request.resource_type and filter_type.lower() in request.resource_type.lower():
                            requests.append(request)
                    else:
                        requests.append(request)
            return requests

    async def get_request(self, request_id: str) -> Optional[NetworkRequest]:
        """Get specific request by ID."""
        return self._requests.get(request_id)

    async def get_response(self, request_id: str) -> Optional[NetworkResponse]:
        """Get response for a request."""
        return self._responses.get(request_id)

    async def get_response_body(self, tab: Tab, request_id: str) -> Optional[bytes]:
        """Get response body content (tries stored body first, then fetches via CDP)."""
        # Check stored body first
        response = self._responses.get(request_id)
        if response and response.body:
            return response.body

        # Fallback: fetch from browser
        try:
            request_id_obj = uc.cdp.network.RequestId(request_id)
            result = await asyncio.wait_for(
                tab.send(uc.cdp.network.get_response_body(request_id=request_id_obj)),
                timeout=self.BODY_FETCH_TIMEOUT,
            )
            if result:
                body, base64_encoded = result
                if base64_encoded:
                    return base64.b64decode(body)
                else:
                    return body.encode("utf-8")
        except (asyncio.TimeoutError, Exception):
            pass
        return None

    async def modify_headers(self, tab: Tab, headers: Dict[str, str]):
        """Modify request headers for future requests."""
        try:
            headers_obj = uc.cdp.network.Headers(headers)
            await tab.send(uc.cdp.network.set_extra_http_headers(headers=headers_obj))
            return True
        except Exception as e:
            raise Exception(f"Failed to modify headers: {str(e)}")

    async def set_user_agent(self, tab: Tab, user_agent: str):
        """Set custom user agent."""
        try:
            await tab.send(uc.cdp.network.set_user_agent_override(user_agent=user_agent))
            return True
        except Exception as e:
            raise Exception(f"Failed to set user agent: {str(e)}")

    async def export_to_json(self, instance_id: str, filepath: str) -> bool:
        """Export network data to JSON file."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            request_ids = self._instance_requests.get(instance_id, [])
            data = {"requests": [], "responses": []}

            for req_id in request_ids:
                if req_id in self._requests:
                    req = self._requests[req_id]
                    data["requests"].append({
                        "request_id": req.request_id,
                        "url": req.url,
                        "method": req.method,
                        "headers": req.headers,
                        "cookies": req.cookies,
                        "post_data": req.post_data,
                        "resource_type": req.resource_type,
                        "timestamp": req.timestamp.isoformat(),
                    })

                if req_id in self._responses:
                    resp = self._responses[req_id]
                    data["responses"].append({
                        "request_id": resp.request_id,
                        "status": resp.status,
                        "headers": resp.headers,
                        "content_type": resp.content_type,
                        "body": base64.b64encode(resp.body).decode('utf-8') if resp.body else None,
                        "timestamp": resp.timestamp.isoformat(),
                    })

            Path(filepath).write_text(json.dumps(data, indent=2))
            return True

    async def import_from_json(self, instance_id: str, filepath: str) -> bool:
        """Import network data from JSON file."""
        data = json.loads(Path(filepath).read_text())

        lock = self._get_instance_lock(instance_id)
        async with lock:
            if instance_id not in self._instance_requests:
                self._instance_requests[instance_id] = []

            for req_data in data.get("requests", []):
                req = NetworkRequest(
                    request_id=req_data["request_id"],
                    instance_id=instance_id,
                    url=req_data["url"],
                    method=req_data["method"],
                    headers=req_data["headers"],
                    cookies=req_data["cookies"],
                    post_data=req_data.get("post_data"),
                    resource_type=req_data.get("resource_type"),
                    timestamp=datetime.fromisoformat(req_data["timestamp"]),
                )
                self._requests[req.request_id] = req
                if req.request_id not in self._instance_requests[instance_id]:
                    self._instance_requests[instance_id].append(req.request_id)

            for resp_data in data.get("responses", []):
                resp = NetworkResponse(
                    request_id=resp_data["request_id"],
                    status=resp_data["status"],
                    headers=resp_data["headers"],
                    content_type=resp_data.get("content_type"),
                    body=base64.b64decode(resp_data["body"]) if resp_data.get("body") else None,
                    timestamp=datetime.fromisoformat(resp_data["timestamp"]),
                )
                self._responses[resp.request_id] = resp

            return True

    async def enable_cache(self, tab: Tab, enabled: bool = True):
        """Enable or disable cache."""
        try:
            await tab.send(uc.cdp.network.set_cache_disabled(cache_disabled=not enabled))
            return True
        except Exception as e:
            raise Exception(f"Failed to set cache state: {str(e)}")

    async def clear_browser_cache(self, tab: Tab):
        """Clear browser cache."""
        try:
            await tab.send(uc.cdp.network.clear_browser_cache())
            return True
        except Exception as e:
            raise Exception(f"Failed to clear cache: {str(e)}")

    async def clear_cookies(self, tab: Tab, url: Optional[str] = None):
        """Clear cookies."""
        try:
            if url:
                cookies = await tab.send(uc.cdp.network.get_cookies(urls=[url]))
                for cookie in cookies:
                    await tab.send(
                        uc.cdp.network.delete_cookies(
                            name=cookie.name,
                            url=url
                        )
                    )
            else:
                await tab.send(uc.cdp.network.clear_browser_cookies())
            return True
        except Exception as e:
            raise Exception(f"Failed to clear cookies: {str(e)}")

    async def set_cookie(self, tab: Tab, cookie: Dict[str, Any]):
        """Set a cookie."""
        try:
            await tab.send(uc.cdp.network.set_cookie(**cookie))
            return True
        except Exception as e:
            raise Exception(f"Failed to set cookie: {str(e)}")

    async def get_cookies(self, tab: Tab, urls: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get cookies."""
        try:
            if urls:
                result = await tab.send(uc.cdp.network.get_cookies(urls=urls))
            else:
                result = await tab.send(uc.cdp.network.get_all_cookies())
            if isinstance(result, dict):
                return result.get("cookies", [])
            elif isinstance(result, list):
                return result
            else:
                return []
        except Exception as e:
            raise Exception(f"Failed to get cookies: {str(e)}")

    async def emulate_network_conditions(
        self,
        tab: Tab,
        offline: bool = False,
        latency: int = 0,
        download_throughput: int = -1,
        upload_throughput: int = -1,
    ):
        """Emulate network conditions."""
        try:
            await tab.send(
                uc.cdp.network.emulate_network_conditions(
                    offline=offline,
                    latency=latency,
                    download_throughput=download_throughput,
                    upload_throughput=upload_throughput,
                )
            )
            return True
        except Exception as e:
            raise Exception(f"Failed to emulate network conditions: {str(e)}")

    async def clear_instance_data(self, instance_id: str):
        """Clear all network data for an instance."""
        lock = self._get_instance_lock(instance_id)
        async with lock:
            if instance_id in self._instance_requests:
                for req_id in self._instance_requests[instance_id]:
                    self._requests.pop(req_id, None)
                    self._responses.pop(req_id, None)
                del self._instance_requests[instance_id]
            self._instance_filters.pop(instance_id, None)

        # Clean up the per-instance lock itself
        async with self._global_lock:
            self._instance_locks.pop(instance_id, None)
