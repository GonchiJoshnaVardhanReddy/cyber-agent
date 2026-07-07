"""agent/tools/search.py — Web search + CVE/CWE search tools."""
from __future__ import annotations

import json
import os
import urllib.parse

import httpx

from .registry import Tool, ToolResult


def _duckduckgo_handler(query: str, max_results: int = 8) -> ToolResult:
    """Search DuckDuckGo HTML (no API key required)."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "Mozilla/5.0"})
        # Parse result snippets (very simple regex)
        import re
        results = []
        for match in re.finditer(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.+?)</a>.*?'
            r'<a[^>]+class="result__snippet"[^>]*>(.+?)</a>',
            resp.text, re.DOTALL,
        ):
            href = match.group(1)
            title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
            snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()
            # DDG wraps URLs in a redirect
            if "uddg=" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    href = urllib.parse.unquote(m.group(1))
            results.append({"title": title, "url": href, "snippet": snippet})
            if len(results) >= max_results:
                break
        if not results:
            return ToolResult(success=True, output=f"No results for: {query}")
        output_lines = [f"Search results for '{query}' ({len(results)} results):"]
        for i, r in enumerate(results, 1):
            output_lines.append(f"\n{i}. {r['title']}\n   URL: {r['url']}\n   {r['snippet'][:200]}")
        return ToolResult(success=True, output="\n".join(output_lines), data={"results": results})
    except Exception as e:
        return ToolResult(success=False, output=f"Search error: {e}", error=str(e))


WEB_SEARCH_TOOL = Tool(
    name="web_search",
    description=(
        "Search the web using DuckDuckGo (no API key required). Use for CVE research, "
        "OSINT, looking up exploit details, finding documentation, etc."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Maximum results to return", "default": 8},
        },
        "required": ["query"],
    },
    handler=_duckduckgo_handler,
)


def _cve_search_handler(cve_id: str) -> ToolResult:
    """Look up a CVE by ID via the NVD API (no key required for low rate)."""
    cve_id = cve_id.upper().strip()
    if not cve_id.startswith("CVE-"):
        return ToolResult(success=False, output="Invalid CVE ID format. Expected CVE-YYYY-NNNN.", error="bad_format")
    try:
        url = f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}"
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, headers={"User-Agent": "cyber-agent/0.1"})
        if resp.status_code != 200:
            return ToolResult(success=False, output=f"NVD API returned {resp.status_code}", error="api_error")
        data = resp.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return ToolResult(success=False, output=f"CVE not found: {cve_id}", error="not_found")
        cve = vulns[0]["cve"]
        descriptions = cve.get("descriptions", [])
        desc_en = next((d["value"] for d in descriptions if d["lang"] == "en"), "")
        # CVSS
        metrics = cve.get("metrics", {})
        cvss_score = None
        cvss_severity = None
        for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metrics.get(key):
                cvss_data = metrics[key][0]["cvssData"]
                cvss_score = cvss_data.get("baseScore")
                cvss_severity = cvss_data.get("baseSeverity", metrics[key][0].get("baseSeverity"))
                break
        # References
        refs = [r["url"] for r in cve.get("references", [])[:5]]
        # Weaknesses (CWE)
        cwes = []
        for w in cve.get("weaknesses", []):
            for d in w.get("description", []):
                if d["lang"] == "en" and d["value"] not in cwes:
                    cwes.append(d["value"])

        output = (
            f"CVE: {cve_id}\n"
            f"Published: {cve.get('published', 'unknown')}\n"
            f"CVSS: {cvss_score} ({cvss_severity})\n"
            f"CWEs: {', '.join(cwes) or 'none'}\n\n"
            f"Description:\n{desc_en}\n\n"
            f"References:\n" + "\n".join(f"  - {r}" for r in refs)
        )
        return ToolResult(success=True, output=output, data={
            "cve_id": cve_id, "cvss": cvss_score, "cwes": cwes, "references": refs,
        })
    except Exception as e:
        return ToolResult(success=False, output=f"CVE search error: {e}", error=str(e))


CVE_SEARCH_TOOL = Tool(
    name="cve_search",
    description=(
        "Look up a CVE by ID (e.g., CVE-2024-1234) via the NVD API. Returns description, "
        "CVSS score, CWE classifications, and references. Useful for researching "
        "vulnerabilities found during testing."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cve_id": {"type": "string", "description": "CVE identifier, e.g., CVE-2024-1234"},
        },
        "required": ["cve_id"],
    },
    handler=_cve_search_handler,
)


SEARCH_TOOLS = [WEB_SEARCH_TOOL, CVE_SEARCH_TOOL]
