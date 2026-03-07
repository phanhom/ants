"""Append a todo item to the ant's todo list (todos/items.jsonl)."""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

# In container ANT_BASE_DIR is /runtime/volumes/<agent_id>; fallback for local
BASE = Path(os.getenv("ANT_BASE_DIR", os.getenv("ANTS_VOLUMES_ROOT", ".")))

TOOL_NAME = "append_todo"
TOOL_DESCRIPTION = "Add a todo item for this ant. Stored in trace and visible in status."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title of the todo"},
        "status": {"type": "string", "description": "pending, in_progress, or completed", "default": "pending"},
    },
    "required": ["title"],
}


def run(title: str, status: str = "pending") -> str:
    base = Path(os.getenv("ANT_BASE_DIR", "."))
    if not base.is_absolute() or not base.exists():
        base = Path("/tmp/ants_volumes") / os.getenv("ANT_AGENT_ID", "unknown")
    todo_dir = base / "todos"
    todo_dir.mkdir(parents=True, exist_ok=True)
    path = todo_dir / "items.jsonl"
    ts = datetime.now(timezone.utc).isoformat()
    row = {"ts": ts, "title": title, "status": status}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return f"Todo added: {title} ({status})"
