"""Write content to a file under the ant workspace. Path is relative to /workspace."""

import os
from pathlib import Path

WORKSPACE = Path(os.getenv("ANT_WORKSPACE", "/workspace"))

TOOL_NAME = "write_file"
TOOL_DESCRIPTION = "Write content to a file under the workspace. Path is relative to workspace; creates parent dirs if needed."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative path under workspace"},
        "content": {"type": "string", "description": "Content to write"},
    },
    "required": ["path", "content"],
}


def run(path: str, content: str) -> str:
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        return "Error: path must be inside workspace"
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Wrote {path} ({len(content)} chars)"
    except Exception as e:
        return f"Error writing file: {e}"
