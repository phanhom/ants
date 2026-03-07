"""
AIP send layer: retry, backoff, and timeouts for POST /aip.
Designed for global use: minimize failure rate under 5xx, timeouts, and transient errors.
Public API: send_aip, async_send_aip (single); send_aip_batch, async_send_aip_batch (parallel).

Logging: stdlib logging. One built-in id only, aip_id (from body). Set AIP_PROTOCOL_LOG=1 to
enable INFO. Pass logger= to fuse with your app; pass log_extra= for trace_id, agent_id, etc.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

_default_logger = logging.getLogger("ants.protocol.send")

if os.getenv("AIP_PROTOCOL_LOG", "").strip().lower() in ("1", "true", "yes") or os.getenv(
    "ANTS_PROTOCOL_LOG", ""
).strip().lower() in ("1", "true", "yes"):
    _default_logger.setLevel(logging.INFO)


def _body_log_extra(body: dict[str, Any]) -> dict[str, Any]:
    """Library-only: extract aip_id from body. All other context (trace_id, agent_id) via log_extra."""
    return {"aip_id": body.get("aip_id") or ""}


def _extra_suffix(extra: dict[str, Any]) -> str:
    """Format extra as key=value for log message so grep on any id works."""
    parts = []
    for k, v in extra.items():
        if v is not None and v != "" and not isinstance(v, (dict, list)):
            parts.append(f"{k}={v}")
    return " " + " ".join(parts) if parts else ""

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
    *,
    log_extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """
    Send AIP message (sync). Retries with exponential backoff on 5xx, timeout, connection errors.
    Returns parsed JSON response; raises on final failure.
    Optional: logger= to use your logger; log_extra= to add fields to every log record.
    """
    import httpx

    p = params or SendParams()
    log = logger if logger is not None else _default_logger
    url = f"{base_url.rstrip('/')}/aip"
    extra = {**_body_log_extra(body), **(log_extra or {})}
    if log.isEnabledFor(logging.INFO):
        log.info(
            "send_aip start url=%s action=%s%s",
            url,
            body.get("action", ""),
            _extra_suffix(extra),
            extra=extra,
        )
    t0 = time.perf_counter()
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
                    duration_ms = round((time.perf_counter() - t0) * 1000)
                    if log.isEnabledFor(logging.INFO):
                        log.info(
                            "send_aip ok url=%s status=%s duration_ms=%s%s",
                            url,
                            r.status_code,
                            duration_ms,
                            _extra_suffix(extra),
                            extra=extra,
                        )
                    return r.json()
                if 400 <= r.status_code < 500:
                    r.raise_for_status()
                last_exc = RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:200]}")
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code if e.response is not None else None
            last_exc = e
            if last_status is not None and 400 <= last_status < 500:
                if log.isEnabledFor(logging.INFO):
                    log.info(
                        "send_aip client_error url=%s status=%s%s",
                        url,
                        last_status,
                        _extra_suffix(extra),
                        extra=extra,
                    )
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, OSError) as e:
            last_exc = e
            last_status = None

        if attempt < p.max_retries - 1:
            delay = p.backoff_delay(attempt)
            if log.isEnabledFor(logging.INFO):
                log.info(
                    "send_aip retry url=%s attempt=%s next_delay_s=%s%s",
                    url,
                    attempt + 1,
                    round(delay, 2),
                    _extra_suffix(extra),
                    extra=extra,
                )
            time.sleep(delay)

    if log.isEnabledFor(logging.INFO):
        log.info(
            "send_aip failed url=%s attempts=%s status=%s error=%s%s",
            url,
            p.max_retries,
            last_status,
            type(last_exc).__name__ if last_exc else "",
            _extra_suffix(extra),
            extra=extra,
        )
    raise (last_exc or RuntimeError("send_aip failed after retries"))


def send_aip_batch(
    requests: list[tuple[str, dict[str, Any]]],
    params: SendParams | None = None,
    *,
    max_workers: int | None = None,
    log_extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> list[dict[str, Any] | BaseException]:
    """
    Send multiple AIP messages in parallel (sync). Uses a thread pool; each call
    uses send_aip with the same retry/backoff semantics. Returns list of
    response dicts or exceptions in the same order as requests.
    Optional: logger=, log_extra=.
    """
    p = params or SendParams()
    log = logger if logger is not None else _default_logger
    n = len(requests)
    if n == 0:
        return []
    extra = {**_body_log_extra(requests[0][1] if requests else {}), **(log_extra or {})}
    if log.isEnabledFor(logging.INFO):
        log.info("send_aip_batch start n=%s%s", n, _extra_suffix(extra), extra=extra)
    t0 = time.perf_counter()
    max_workers = min(max_workers or n, n) if max_workers is not None else n
    out: dict[int, dict[str, Any] | BaseException] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_idx = {
            pool.submit(send_aip, base_url, body, p): i
            for i, (base_url, body) in enumerate(requests)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                out[idx] = future.result()
            except BaseException as e:
                out[idx] = e
    results = [out[i] for i in range(n)]
    ok = sum(1 for r in results if not isinstance(r, BaseException))
    if log.isEnabledFor(logging.INFO):
        log.info(
            "send_aip_batch done n=%s ok=%s failed=%s duration_ms=%s%s",
            n,
            ok,
            n - ok,
            round((time.perf_counter() - t0) * 1000),
            _extra_suffix(extra),
            extra=extra,
        )
    return results


async def async_send_aip(
    base_url: str,
    body: dict[str, Any],
    params: SendParams | None = None,
    *,
    log_extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> dict[str, Any]:
    """
    Send AIP message (async). Same retry/backoff semantics as send_aip.
    For use in FastAPI / asyncio. Optional: logger=, log_extra=.
    """
    import httpx

    p = params or SendParams()
    log = logger if logger is not None else _default_logger
    url = f"{base_url.rstrip('/')}/aip"
    extra = {**_body_log_extra(body), **(log_extra or {})}
    if log.isEnabledFor(logging.INFO):
        log.info(
            "async_send_aip start url=%s action=%s%s",
            url,
            body.get("action", ""),
            _extra_suffix(extra),
            extra=extra,
        )
    t0 = time.perf_counter()
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
                    duration_ms = round((time.perf_counter() - t0) * 1000)
                    if log.isEnabledFor(logging.INFO):
                        log.info(
                            "async_send_aip ok url=%s status=%s duration_ms=%s%s",
                            url,
                            r.status_code,
                            duration_ms,
                            _extra_suffix(extra),
                            extra=extra,
                        )
                    return r.json()
                if 400 <= r.status_code < 500:
                    r.raise_for_status()
                last_exc = RuntimeError(f"HTTP {r.status_code}: {(r.text or '')[:200]}")
        except httpx.HTTPStatusError as e:
            last_status = e.response.status_code if e.response is not None else None
            last_exc = e
            if last_status is not None and 400 <= last_status < 500:
                if log.isEnabledFor(logging.INFO):
                    log.info(
                        "async_send_aip client_error url=%s status=%s%s",
                        url,
                        last_status,
                        _extra_suffix(extra),
                        extra=extra,
                    )
                raise
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError, OSError) as e:
            last_exc = e
            last_status = None

        if attempt < p.max_retries - 1:
            delay = p.backoff_delay(attempt)
            if log.isEnabledFor(logging.INFO):
                log.info(
                    "async_send_aip retry url=%s attempt=%s next_delay_s=%s%s",
                    url,
                    attempt + 1,
                    round(delay, 2),
                    _extra_suffix(extra),
                    extra=extra,
                )
            await asyncio.sleep(delay)

    if log.isEnabledFor(logging.INFO):
        log.info(
            "async_send_aip failed url=%s attempts=%s status=%s error=%s%s",
            url,
            p.max_retries,
            last_status,
            type(last_exc).__name__ if last_exc else "",
            _extra_suffix(extra),
            extra=extra,
        )
    raise (last_exc or RuntimeError("async_send_aip failed after retries"))


async def async_send_aip_batch(
    requests: list[tuple[str, dict[str, Any]]],
    params: SendParams | None = None,
    *,
    log_extra: dict[str, Any] | None = None,
    logger: logging.Logger | None = None,
) -> list[dict[str, Any] | BaseException]:
    """
    Send multiple AIP messages in parallel (async). Each (base_url, body) uses
    the same retry/backoff semantics as async_send_aip. Optional: logger=, log_extra=.
    """
    p = params or SendParams()
    log = logger if logger is not None else _default_logger
    n = len(requests)
    extra = {**_body_log_extra(requests[0][1] if requests else {}), **(log_extra or {})}
    if log.isEnabledFor(logging.INFO) and n:
        log.info("async_send_aip_batch start n=%s%s", n, _extra_suffix(extra), extra=extra)
    t0 = time.perf_counter()
    tasks = [async_send_aip(base_url, body, p) for base_url, body in requests]
    results = list(await asyncio.gather(*tasks, return_exceptions=True))
    if log.isEnabledFor(logging.INFO) and n:
        ok = sum(1 for r in results if not isinstance(r, BaseException))
        log.info(
            "async_send_aip_batch done n=%s ok=%s failed=%s duration_ms=%s%s",
            n,
            ok,
            n - ok,
            round((time.perf_counter() - t0) * 1000),
            _extra_suffix(extra),
            extra=extra,
        )
    return results
