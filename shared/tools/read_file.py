"""Read a file under the ant workspace. Path is relative to /workspace."""

import os
from pathlib import Path

WORKSPACE = Path(os.getenv("ANT_WORKSPACE", "/workspace"))

TOOL_NAME = "read_file"
TOOL_DESCRIPTION = "Read the contents of a file under the workspace. Path must be relative to workspace (e.g. 'src/main.py')."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative path to file under workspace"},
    },
    "required": ["path"],
}


def run(path: str) -> str:
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        return "Error: path must be inside workspace"
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"
