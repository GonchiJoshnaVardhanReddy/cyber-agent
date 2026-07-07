"""agent/tools/web.py — HTTP client + web crawler."""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from .registry import Tool, ToolResult


def _http_request_handler(url: str, method: str = "GET", headers: dict | None = None,
                          body: str | None = None, timeout: int = 30,
                          max_response_size: int = 10_485_760,
                          follow_redirects: bool = True) -> ToolResult:
    """Make an HTTP request. Returns status, headers, and (truncated) body."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=follow_redirects) as client:
            req_kwargs: dict = {}
            if headers:
                req_kwargs["headers"] = headers
            if body:
                req_kwargs["content"] = body
            resp = client.request(method.upper(), url, **req_kwargs)
            # Bounded read
            content = resp.content[:max_response_size]
            try:
                text = content.decode(resp.encoding or "utf-8", errors="replace")
            except (LookupError, TypeError):
                text = content.decode("utf-8", errors="replace")
            # Truncate for LLM
            text_truncated = text[:8000]
            if len(text) > 8000:
                text_truncated += f"\n... [truncated, {len(text)} total chars]"
            output = (
                f"HTTP {resp.status_code} {resp.reason_phrase}\n"
                f"URL: {resp.url}\n"
                f"Headers:\n" + "\n".join(f"  {k}: {v}" for k, v in resp.headers.items()) + "\n\n"
                f"Body:\n{text_truncated}"
            )
            return ToolResult(
                success=True, output=output,
                data={"status": resp.status_code, "headers": dict(resp.headers),
                      "body_len": len(text)},
            )
    except httpx.HTTPError as e:
        return ToolResult(success=False, output=f"HTTP error: {e}", error=str(e))


HTTP_TOOL = Tool(
    name="http_request",
    description=(
        "Send an HTTP request to a URL. Use for API testing, web app recon, and "
        "vulnerability validation. Method defaults to GET. Headers is a dict of "
        "request headers. Body is sent as-is (set Content-Type header accordingly). "
        "Responses are truncated to 8KB for readability."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL including scheme"},
            "method": {"type": "string", "description": "HTTP method: GET, POST, PUT, DELETE, etc.", "default": "GET"},
            "headers": {"type": "object", "description": "Request headers", "default": {}},
            "body": {"type": "string", "description": "Request body (raw)", "default": ""},
            "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            "follow_redirects": {"type": "boolean", "description": "Follow 3xx redirects", "default": True},
        },
        "required": ["url"],
    },
    handler=_http_request_handler,
    requires_scope_target="url",
)


# ── Web crawler ─────────────────────────────────────────────────────────

def _crawl_handler(start_url: str, max_pages: int = 10, max_depth: int = 2,
                   timeout: int = 20) -> ToolResult:
    """Crawl a website starting from start_url. Returns discovered links + page metadata."""
    visited: set[str] = set()
    queue: list[tuple[str, int]] = [(start_url, 0)]
    results: list[dict] = []
    base_domain = urlparse(start_url).netloc

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        while queue and len(visited) < max_pages:
            url, depth = queue.pop(0)
            if url in visited or depth > max_depth:
                continue
            visited.add(url)
            try:
                resp = client.get(url)
            except httpx.HTTPError as e:
                results.append({"url": url, "error": str(e)})
                continue
            page_info = {
                "url": str(resp.url),
                "status": resp.status_code,
                "title": _extract_title(resp.text),
                "depth": depth,
                "links_found": 0,
            }
            # Extract same-origin links
            if depth < max_depth:
                links = _extract_links(resp.text, str(resp.url), base_domain)
                page_info["links_found"] = len(links)
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))
            results.append(page_info)

    output_lines = [f"Crawled {len(results)} pages starting from {start_url}:"]
    for r in results:
        if "error" in r:
            output_lines.append(f"  [ERR] {r['url']} — {r['error']}")
        else:
            output_lines.append(f"  [{r['status']}] {r['url']} — {r['title']} (depth {r['depth']}, {r['links_found']} links)")
    return ToolResult(success=True, output="\n".join(output_lines), data={"pages": results})


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip()[:100] if match else "(no title)"


def _extract_links(html: str, base_url: str, base_domain: str) -> list[str]:
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html, re.IGNORECASE):
        href = match.group(1)
        if href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        full_url = urljoin(base_url, href)
        if urlparse(full_url).netloc == base_domain:
            links.append(full_url.split("#")[0])
    return list(dict.fromkeys(links))  # dedupe, preserve order


CRAWL_TOOL = Tool(
    name="web_crawl",
    description=(
        "Crawl a website starting from a URL. Discovers pages, titles, and links "
        "(same-origin only). Useful for mapping a web app's surface before testing. "
        "Respects max_pages and max_depth to avoid runaway crawls."
    ),
    parameters={
        "type": "object",
        "properties": {
            "start_url": {"type": "string", "description": "URL to start crawling from"},
            "max_pages": {"type": "integer", "description": "Maximum pages to visit", "default": 10},
            "max_depth": {"type": "integer", "description": "Maximum link depth from start", "default": 2},
            "timeout": {"type": "integer", "description": "Per-request timeout in seconds", "default": 20},
        },
        "required": ["start_url"],
    },
    handler=_crawl_handler,
    requires_scope_target="start_url",
)


WEB_TOOLS = [HTTP_TOOL, CRAWL_TOOL]
