"""Search for text in the workspace (grep-style). Path glob optional."""

import fnmatch
import os
from pathlib import Path

WORKSPACE = Path(os.getenv("ANT_WORKSPACE", "/workspace"))

TOOL_NAME = "search_codebase"
TOOL_DESCRIPTION = (
    "Search for a string in files under the workspace. "
    "Returns matching lines with file path and line number. "
    "Use path_glob to limit to e.g. '*.py' or '*.yaml'."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "description": "String to search for"},
        "path_glob": {"type": "string", "description": "Optional glob (e.g. '*.py', '*.md'). Omit to search all files."},
        "max_lines": {"type": "integer", "description": "Max lines to return (default 100)", "default": 100},
    },
    "required": ["query"],
}

DEFAULT_MAX_LINES = 100
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}


def run(query: str, path_glob: str | None = None, max_lines: int = DEFAULT_MAX_LINES) -> str:
    if not query.strip():
        return "Error: query must be non-empty"
    work = WORKSPACE.resolve()
    if not work.exists():
        return "Error: workspace not found"
    results: list[str] = []
    try:
        for root, dirs, files in os.walk(work):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rel_root = Path(root).relative_to(work) if work != Path(root) else Path(".")
            for f in files:
                if path_glob and not fnmatch.fnmatch(f, path_glob):
                    continue
                path = rel_root / f
                try:
                    text = (work / path).read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for i, line in enumerate(text.splitlines(), 1):
                    if query in line:
                        results.append(f"{path}:{i}:{line.strip()[:200]}")
                        if len(results) >= max_lines:
                            return "\n".join(results)
        return "\n".join(results) if results else "No matches found."
    except Exception as e:
        return f"Error searching: {e}"
