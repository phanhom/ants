"""Run a web search and return snippets/links. For research and discovery."""

TOOL_NAME = "web_search"
TOOL_DESCRIPTION = (
    "Search the web and return titles, snippets, and URLs. "
    "Use for research, finding docs, or checking current information."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "Search query"},
        "max_results": {"type": "integer", "description": "Max results to return (default 5)", "default": 5},
    },
    "required": ["query"],
}

DEFAULT_MAX = 5


def run(query: str, max_results: int = DEFAULT_MAX) -> str:
    if not query.strip():
        return "Error: query must be non-empty"
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            lines.append(f"{i}. {title}\n   {body[:300]}...\n   {href}")
        return "\n\n".join(lines)
    except ImportError:
        try:
            import httpx
            # Fallback: request to duckduckgo html and parse (fragile)
            with httpx.Client(timeout=10, follow_redirects=True) as client:
                r = client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json"},
                )
                r.raise_for_status()
                data = r.json()
            abstracts = data.get("AbstractText") or ""
            related = data.get("RelatedTopics") or []
            out = [abstracts] if abstracts else []
            for i, t in enumerate(related[:max_results]):
                if isinstance(t, dict) and t.get("Text"):
                    out.append(f"{i+1}. {t.get('Text', '')} {t.get('FirstURL', '')}")
                elif isinstance(t, str):
                    out.append(str(t))
            return "\n".join(out) if out else "No results (install duckduckgo-search for better results)."
        except Exception as e:
            return f"Error: {e}. Install duckduckgo-search for web search."
    except Exception as e:
        return f"Error searching: {e}"
