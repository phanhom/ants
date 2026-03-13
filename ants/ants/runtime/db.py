"""Trace writer for Ants agents. Posts to Nest /v1/traces endpoint."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

_nest_url: str | None = None


def _get_nest_url() -> str:
    global _nest_url
    if _nest_url is None:
        _nest_url = (os.getenv("NEST_URL") or "").strip()
    return _nest_url


def init_db() -> None:
    """No-op for workers — Nest owns the database."""
    url = _get_nest_url()
    if url:
        log.info("Trace writes will POST to %s/v1/traces", url)
    else:
        log.info("NEST_URL not set — trace writes disabled")


def write_trace(agent_id: str, trace_type: str, payload: dict[str, Any]) -> bool:
    url = _get_nest_url()
    if not url:
        return False
    try:
        import httpx
        ts = datetime.now(timezone.utc).isoformat()
        body = {
            "agent_id": agent_id,
            "trace_type": trace_type,
            "ts": ts,
            **payload,
        }
        with httpx.Client(timeout=5) as client:
            resp = client.post(f"{url}/v1/traces", json=body)
            return resp.status_code == 200
    except Exception:
        log.debug("write_trace to Nest failed for %s/%s", agent_id, trace_type)
        return False
