"""Worker HTTP server: two interfaces only — AIP conversation and status/progress."""

from __future__ import annotations

import os
import threading

from fastapi import FastAPI, HTTPException, Query, Request

from aip import AIPAction, AIPMessage, AIPStatus
from ants.runtime.status import StatusScope
from ants.runtime.config import load_agent_config, load_all_agent_configs
from ants.runtime.status import build_worker_self_status, build_worker_subtree_status
from ants.runtime.trace_log import trace_log
from ants.runtime.traces import append_aip_message, ensure_trace_dirs, write_log

WORKER_PORT = 22001

app = FastAPI(title="Ants Worker", version="0.1.0")


def _run_bootstrap_loop() -> None:
    """Run tool discovery and heartbeat in background."""
    from ants.agents.bootstrap import run_bootstrap
    run_bootstrap(poll=True)


@app.on_event("startup")
def startup() -> None:
    config = load_agent_config()
    ensure_trace_dirs(config.agent_id)
    write_log(config.agent_id, "runtime.jsonl", {"event": "worker_started", "port": WORKER_PORT})
    thread = threading.Thread(target=_run_bootstrap_loop, daemon=True)
    thread.start()


# ---------- Interface 1: Container-to-container conversation (AIP) ----------

@app.post("/aip")
@app.post("/v1/aip")
async def aip_receive(body: dict) -> dict:
    """
    Receive an AIP message from another ant (same host or remote).
    Persists to aip/messages.jsonl and returns ack. Cross-server: caller uses this ant's base URL.
    """
    config = load_agent_config()
    try:
        msg = AIPMessage.model_validate(body)
    except Exception as e:
        raise HTTPException(422, f"Invalid AIP message: {e}") from e
    if msg.to != config.agent_id and msg.to != "*":
        raise HTTPException(400, f"This ant is {config.agent_id}, message to={msg.to}")
    payload = msg.model_dump(by_alias=True, mode="json")
    append_aip_message(config.agent_id, "in", payload)
    msg.status = AIPStatus.in_progress
    if msg.action == AIPAction.assign_task and msg.payload:
        payload_obj = msg.payload or {}
        trace_log(
            "assign_task",
            trace_id=payload_obj.get("trace_id"),
            agent_id=config.agent_id,
            from_agent=msg.from_agent,
        )
        def _run_task():
            try:
                from ants.agents.runner import run_task
                run_task(config.agent_id, msg.payload)
            except Exception:
                pass
        threading.Thread(target=_run_task, daemon=True).start()
    return {
        "ok": True,
        "message_id": msg.message_id,
        "to": config.agent_id,
        "status": "received",
    }


# ---------- Interface 2: Own work info, status, progress ----------

@app.get("/status")
@app.get("/v1/status")
async def status(
    request: Request,
    scope: StatusScope = Query(StatusScope.self_scope),
) -> dict:
    """Return self status by default, or a recursive subtree if requested."""
    config = load_agent_config()
    request_base_url = str(request.base_url).rstrip("/")
    if scope == StatusScope.subtree:
        agents = load_all_agent_configs()
        subtree = await build_worker_subtree_status(
            config,
            agents=agents,
            port=WORKER_PORT,
            request_base_url=request_base_url,
        )
        return subtree.model_dump(mode="json")
    status_doc = build_worker_self_status(config, port=WORKER_PORT, request_base_url=request_base_url)
    return status_doc.model_dump(mode="json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=WORKER_PORT)
