"""Helpers for per-ant trace directories and JSONL persistence."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TRACE_DIR_NAMES = (
    "workspace",
    "logs",
    "conversations",
    "aip",
    "todos",
    "reports",
    "context",
)


def utc_now_iso() -> str:
    """Return ISO-8601 UTC time."""
    return datetime.now(timezone.utc).isoformat()


def get_agent_base_dir(agent_id: str) -> Path:
    """Resolve a per-ant base trace directory. Works in container and on host."""
    explicit = os.getenv("ANT_BASE_DIR")
    if explicit:
        return Path(explicit)
    env_root = os.getenv("ANTS_VOLUMES_ROOT")
    if env_root:
        return Path(env_root) / agent_id
    # Local run: use cwd/volumes or /tmp/ants_volumes
    cwd_volumes = Path.cwd() / "volumes"
    if cwd_volumes.exists() or Path.cwd() == Path("/app"):
        return cwd_volumes / agent_id
    return Path("/tmp/ants_volumes") / agent_id


def ensure_trace_dirs(agent_id: str) -> Path:
    """Create standard trace directories for the ant."""
    base = get_agent_base_dir(agent_id)
    for name in TRACE_DIR_NAMES:
        (base / name).mkdir(parents=True, exist_ok=True)
    return base


def append_jsonl(file_path: Path, payload: dict[str, Any]) -> None:
    """Append a JSON line to a trace file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def write_log(agent_id: str, filename: str, payload: dict[str, Any]) -> None:
    """Write a structured log entry into the ant trace tree."""
    base = ensure_trace_dirs(agent_id)
    payload = {"ts": utc_now_iso(), **payload}
    append_jsonl(base / "logs" / filename, payload)


def list_recent_jsonl(file_path: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Read the last N JSONL rows from a trace file."""
    if not file_path.exists():
        return []
    lines = file_path.read_text(encoding="utf-8").splitlines()
    items: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def append_aip_message(agent_id: str, direction: str, payload: dict[str, Any]) -> None:
    """Append an AIP message to this ant's aip/messages.jsonl (direction: in|out); dual-write to DB if configured."""
    base = ensure_trace_dirs(agent_id)
    row = {"ts": utc_now_iso(), "direction": direction, **payload}
    append_jsonl(base / "aip" / "messages.jsonl", row)
    try:
        from ants.runtime.db import write_trace
        write_trace(agent_id, "aip", row)
    except Exception:
        pass


def write_trace_dual(agent_id: str, trace_type: str, filename: str, payload: dict[str, Any]) -> None:
    """Write to file (logs or similar) and optionally to DB. trace_type: log, conversation, todo, report."""
    base = ensure_trace_dirs(agent_id)
    row = {"ts": utc_now_iso(), **payload}
    path = base / "logs" / filename if trace_type == "log" else base / trace_type / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, row)
    try:
        from ants.runtime.db import write_trace
        write_trace(agent_id, trace_type, row)
    except Exception:
        pass
