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
    env_root = (os.getenv("ANTS_VOLUMES_ROOT") or "").strip()
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
    """Append a JSON line to a trace file. Uses UTF-8."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_log(agent_id: str, filename: str, payload: dict[str, Any]) -> None:
    """Write a structured log entry into the ant trace tree. Each line includes agent_id (agent name)."""
    base = ensure_trace_dirs(agent_id)
    payload = {"ts": utc_now_iso(), "agent_id": agent_id, **payload}
    append_jsonl(base / "logs" / filename, payload)


_LIST_RECENT_JSONL_DEFAULT_LIMIT = 20
_LIST_RECENT_JSONL_SMALL_FILE_THRESHOLD = 64 * 1024  # 64 KiB


def _read_tail_lines(file_path: Path, limit: int) -> list[str]:
    """Read the last `limit` lines from file in chronological order. O(limit) space."""
    size = file_path.stat().st_size
    if size == 0:
        return []
    block_size = 8192
    with file_path.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        buffer = b""
        lines_collected: list[str] = []

        while pos > 0 and len(lines_collected) < limit:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)
            chunk = f.read(read_size)
            buffer = chunk + buffer
            # Split by newline; treat \r\n and \n
            while True:
                idx = buffer.rfind(b"\n")
                if idx == -1:
                    break
                line_bytes = buffer[idx + 1 :]
                buffer = buffer[:idx]
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if line:
                    lines_collected.append(line)
                if len(lines_collected) >= limit:
                    break
            if len(lines_collected) >= limit:
                break
        # Any remaining buffer is the start of the file (may contain multiple lines).
        if buffer.strip() and len(lines_collected) < limit:
            front_lines = [
                s for s in buffer.decode("utf-8", errors="replace").splitlines()
                if s.strip()
            ]
            lines_collected = front_lines + list(reversed(lines_collected))
        else:
            lines_collected = list(reversed(lines_collected))
        return lines_collected[-limit:] if len(lines_collected) > limit else lines_collected


def list_recent_jsonl(file_path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Read the last N JSONL rows from a trace file. O(limit) for large files."""
    if limit is None:
        limit = _LIST_RECENT_JSONL_DEFAULT_LIMIT
    if not file_path.exists():
        return []
    try:
        stat = file_path.stat()
    except OSError:
        return []
    if stat.st_size <= _LIST_RECENT_JSONL_SMALL_FILE_THRESHOLD:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        lines = lines[-limit:] if len(lines) > limit else lines
    else:
        lines = _read_tail_lines(file_path, limit)
    items: list[dict[str, Any]] = []
    for line in lines:
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return items


def append_aip_message(agent_id: str, direction: str, payload: dict[str, Any]) -> None:
    """Append an AIP message to this ant's aip/messages.jsonl (direction: in|out); dual-write to DB if configured."""
    base = ensure_trace_dirs(agent_id)
    row = {"ts": utc_now_iso(), "agent_id": agent_id, "direction": direction, **payload}
    append_jsonl(base / "aip" / "messages.jsonl", row)
    try:
        from ants.runtime.db import write_trace
        write_trace(agent_id, "aip", row)
    except Exception:
        pass


def write_trace_dual(agent_id: str, trace_type: str, filename: str, payload: dict[str, Any]) -> None:
    """Write to file (logs or similar) and optionally to DB. trace_type: log, conversation, todo, report."""
    base = ensure_trace_dirs(agent_id)
    row = {"ts": utc_now_iso(), "agent_id": agent_id, **payload}
    path = base / "logs" / filename if trace_type == "log" else base / trace_type / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    append_jsonl(path, row)
    try:
        from ants.runtime.db import write_trace
        write_trace(agent_id, trace_type, row)
    except Exception:
        pass
