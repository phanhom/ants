"""Fetch current colony status from the queen to align progress with other workers."""

import json
import os

TOOL_NAME = "get_colony_status"
TOOL_DESCRIPTION = (
    "Fetch the current colony status from the queen: all agents, their progress, "
    "pending todos, last_seen, and work summary. Use to align progress with other workers."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {},
    "required": [],
}


def run() -> str:
    base = os.getenv("ANT_QUEEN_URL", "").rstrip("/")
    if not base:
        return "Error: ANT_QUEEN_URL not set"
    try:
        import httpx
        with httpx.Client(timeout=15.0) as client:
            r = client.get(f"{base}/status", params={"scope": "colony"})
            r.raise_for_status()
            data = r.json()
        return json.dumps(data, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Error fetching colony status: {e}"
