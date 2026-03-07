"""
AIP send layer: retry, backoff, and timeouts for POST /aip.
Designed for global use: minimize failure rate under 5xx, timeouts, and transient errors.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Any

# Defaults tuned for high reliability over many calls; override via SendParams.
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 4  # 1 initial + 3 retries
DEFAULT_BACKOFF_BASE = 1.0
DEFAULT_BACKOFF_MAX = 60.0
DEFAULT_BACKOFF_JITTER = 0.2  # ±20% jitter to avoid thundering herd


@dataclass
class SendParams:
    """Parameters for AIP send; use defaults or override for your deployment."""

    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE
    backoff_max: float = DEFAULT_BACKOFF_MAX
    backoff_jitter: float = DEFAULT_BACKOFF_JITTER
    idempotency_key: str | None = None  # Optional; if set, caller can send in header or payload for dedup

    def backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with cap and jitter."""
        delay = min(self.backoff_max, self.backoff_base * (2 ** attempt))
        jitter = delay * self.backoff_jitter * (2 * random.random() - 1)
        return max(0.0, delay + jitter)


def send_aip(
    base_url: str,
    body: dict[str, Any],
    params: SendParams | None = None,
) -> dict[str, Any]:
    """
    Send AIP message (sync). Retries with exponential backoff on 5xx, timeout, connection errors.
    Returns parsed JSON response; raises on final failure.
    """
    import httpx

    p = params or SendParams()
    url = f"{base_url.rstrip('/')}/aip"
    last_exc: Exception | None = None
    last_status: int | None = None

    for attempt in range(p.max_retries):
        try:
            with httpx.Client(timeout=p.timeout) as client:
                headers = {}
                if p.idempotency_key:
                    headers["Idempotency-Key"] = p.idempotency_key
                r = client.post(url, json=body, headers=headers or None)
                last_status = r.status_code
                if r.is_success:
                    return r.json()
                if 400 <= r.status_code < 500:
                    r.raise_for_status()
                last_exc = RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:200]}")
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code if e.response is not None else None
            last_exc = e
            if last_status is not None and 400 <= last_status < 500:
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, OSError) as e:
            last_exc = e
            last_status = None

        if attempt < p.max_retries - 1:
            delay = p.backoff_delay(attempt)
            time.sleep(delay)

    raise (last_exc or RuntimeError("send_aip failed after retries"))


async def async_send_aip(
    base_url: str,
    body: dict[str, Any],
    params: SendParams | None = None,
) -> dict[str, Any]:
    """
    Send AIP message (async). Same retry/backoff semantics as send_aip.
    For use in FastAPI / asyncio.
    """
    import httpx

    p = params or SendParams()
    url = f"{base_url.rstrip('/')}/aip"
    last_exc: Exception | None = None
    last_status: int | None = None

    for attempt in range(p.max_retries):
        try:
            async with httpx.AsyncClient(timeout=p.timeout) as client:
                headers = {}
                if p.idempotency_key:
                    headers["Idempotency-Key"] = p.idempotency_key
                r = await client.post(url, json=body, headers=headers or None)
                last_status = r.status_code
                if r.is_success:
                    return r.json()
                if 400 <= r.status_code < 500:
                    r.raise_for_status()
                last_exc = RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:200]}")
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code if e.response is not None else None
            last_exc = e
            if last_status is not None and 400 <= last_status < 500:
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, OSError) as e:
            last_exc = e
            last_status = None

        if attempt < p.max_retries - 1:
            delay = p.backoff_delay(attempt)
            await asyncio.sleep(delay)

    raise (last_exc or RuntimeError("async_send_aip failed after retries"))
