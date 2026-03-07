"""Fetch a URL and return the response body as text. Primary way to access the web."""

import re

TOOL_NAME = "fetch_url"
TOOL_DESCRIPTION = (
    "Fetch a URL (HTTP/HTTPS) and return the response body as text. "
    "Use to read web pages, APIs, or docs. Timeout 15s, max 2MB. "
    "HTML is stripped to approximate text content."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Full URL to fetch (e.g. https://example.com/page)"},
    },
    "required": ["url"],
}

TIMEOUT = 15
MAX_BYTES = 2 * 1024 * 1024
MAX_OUT = 50000


def _strip_html(raw: str) -> str:
    """Remove tags and collapse whitespace."""
    raw = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw)
    return raw.strip()


def run(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        import httpx
    except ImportError:
        httpx = None
    if httpx is not None:
        try:
            with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as client:
                r = client.get(url)
                r.raise_for_status()
                text = r.text
                if len(r.content) > MAX_BYTES:
                    text = text[:MAX_BYTES] + "\n... [truncated]"
        except Exception as e:
            return f"Error fetching URL: {e}"
    else:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "AntsBot/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                body = resp.read(MAX_BYTES)
                if resp.read(1):
                    body += b"... [truncated]"
                text = body.decode("utf-8", errors="replace")
        except Exception as e:
            return f"Error fetching URL: {e}"
    if "<" in text and ">" in text:
        try:
            text = _strip_html(text)
        except Exception:
            pass
    return text[:MAX_OUT] if len(text) > MAX_OUT else text
