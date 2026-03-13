"""Replace a string in a file under the ant workspace. Path is relative to /workspace."""

import os
from pathlib import Path

WORKSPACE = Path(os.getenv("ANT_WORKSPACE", "/workspace"))

TOOL_NAME = "edit_file"
TOOL_DESCRIPTION = (
    "Replace old_string with new_string in a file under the workspace. "
    "Use for editing code or config. Path must be relative to workspace. "
    "Fails if old_string is not found (use exact match)."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Relative path to file under workspace"},
        "old_string": {"type": "string", "description": "Exact string to replace"},
        "new_string": {"type": "string", "description": "Replacement string"},
    },
    "required": ["path", "old_string", "new_string"],
}


def run(path: str, old_string: str, new_string: str) -> str:
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        return "Error: path must be inside workspace"
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
        if old_string not in text:
            return f"Error: old_string not found in {path}"
        new_text = text.replace(old_string, new_string, 1)
        p.write_text(new_text, encoding="utf-8")
        return f"Replaced in {path} (1 occurrence)"
    except Exception as e:
        return f"Error editing file: {e}"
