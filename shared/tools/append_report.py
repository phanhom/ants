"""Append a report entry to the ant's reports (reports/reports.jsonl). Dual-writes to DB."""

import json
import os
from pathlib import Path
from datetime import datetime, timezone

TOOL_NAME = "append_report"
TOOL_DESCRIPTION = "Add a work report for this ant. Stored in trace and visible in status. Dual-writes to file and DB."
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Short title of the report"},
        "body": {"type": "string", "description": "Report content or summary", "default": ""},
        "status": {"type": "string", "description": "Optional status (e.g. draft, final)", "default": "final"},
    },
    "required": ["title"],
}


def run(title: str, body: str = "", status: str = "final") -> str:
    base = Path(os.getenv("ANT_BASE_DIR", "."))
    if not base.is_absolute() or not base.exists():
        base = Path("/tmp/ants_volumes") / os.getenv("ANT_AGENT_ID", "unknown")
    report_dir = base / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / "reports.jsonl"
    ts = datetime.now(timezone.utc).isoformat()
    row = {"ts": ts, "title": title, "body": body, "status": status}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    agent_id = os.getenv("ANT_AGENT_ID")
    if agent_id:
        try:
            from ants.runtime.db import write_trace
            write_trace(agent_id, "report", row)
        except Exception:
            pass
    return f"Report added: {title}"
