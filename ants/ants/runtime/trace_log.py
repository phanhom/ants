"""Ants application trace logging: one trace_id per request. Enable with ANTS_TRACE_LOG=1."""

from __future__ import annotations

import logging
import os
from typing import Any

from ants.runtime.traces import utc_now_iso

_logger = logging.getLogger("ants.trace")

if os.getenv("ANTS_TRACE_LOG", "").strip().lower() in ("1", "true", "yes"):
    _logger.setLevel(logging.INFO)


def _suffix(trace_id: str | None, **kwargs: Any) -> str:
    parts = []
    if trace_id:
        parts.append(f"trace_id={trace_id}")
    for k, v in kwargs.items():
        if v is not None and v != "" and not isinstance(v, (dict, list)):
            parts.append(f"{k}={v}")
    return " " + " ".join(parts) if parts else ""


def trace_log(
    event: str,
    *,
    trace_id: str | None = None,
    **kwargs: Any,
) -> None:
    """Log one trace line. Include trace_id and ts (ISO UTC) in extra for Grafana. Caller should pass agent_id."""
    if not _logger.isEnabledFor(logging.INFO):
        return
    extra = {"trace_id": trace_id or "", "ts": utc_now_iso(), **kwargs}
    msg = _suffix(trace_id, **kwargs)
    _logger.info("ants.trace %s%s", event, " " + msg if msg.strip() else "", extra=extra)
