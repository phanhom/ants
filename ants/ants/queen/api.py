"""Queen agent API — receives instructions via AIP, decomposes, and delegates to workers."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from aip import (
    AIPAction,
    AIPMessage,
    AIPStatus,
    SendParams,
    async_send,
    async_send_batch,
)

from ants.runtime.config import get_config_dir, load_agent_config, load_all_agent_configs
from ants.runtime.docker_manager import DockerSpawner, WORKER_SERVICE_PORT
from ants.runtime.models import AgentConfig
from ants.runtime.runtime_config import get_ants_config, load_runtime_config, runtime_config_to_env
from ants.runtime.trace_log import trace_log
from ants.runtime.traces import append_aip_message, ensure_trace_dirs, write_log
from ants.queen.decompose import decompose_instruction

QUEEN_PORT = 22100


def _nest_url() -> str:
    return (os.getenv("NEST_URL") or "http://nest:22000").rstrip("/")


async def _register_with_nest(config: AgentConfig, base_url: str) -> str | None:
    """Register this queen with Nest platform. Returns heartbeat_url."""
    import httpx
    secret = (os.getenv("NEST_SECRET") or "").strip()
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    body = {
        "agent_id": config.agent_id,
        "base_url": base_url,
        "namespace": "default",
        "role": config.role,
        "superior": config.superior,
        "subordinates": config.subordinates,
        "authority_weight": config.authority_weight,
        "display_name": config.display_name,
        "endpoints": {
            "aip": f"{base_url}/v1/aip",
            "status": f"{base_url}/v1/status",
        },
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{_nest_url()}/v1/registry/agents", json=body, headers=headers)
            resp.raise_for_status()
            return resp.json().get("heartbeat_url")
    except Exception as e:
        write_log(config.agent_id, "runtime.jsonl", {"event": "nest_register_failed", "error": str(e)})
        return None


async def _heartbeat_loop(config: AgentConfig, heartbeat_path: str):
    """Send heartbeats to Nest every 10 seconds."""
    import httpx
    from datetime import datetime, timezone
    url = f"{_nest_url()}{heartbeat_path}"
    secret = (os.getenv("NEST_SECRET") or "").strip()
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    async with httpx.AsyncClient(timeout=10, headers=headers) as client:
        while True:
            await asyncio.sleep(10)
            try:
                await client.post(url, json={
                    "ok": True,
                    "lifecycle": "running",
                    "pending_tasks": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except asyncio.CancelledError:
                return
            except Exception:
                pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    config_dir = get_config_dir()
    root_path = config_dir / "creator_decider.json"
    if not root_path.exists():
        raise FileNotFoundError(f"Root config not found: {root_path}")
    root_config = load_agent_config(root_path)
    ensure_trace_dirs(root_config.agent_id)

    app.state.root_config = root_config
    app.state.config_dir = config_dir
    app.state.visible_agents = load_all_agent_configs(config_dir)
    write_log(root_config.agent_id, "runtime.jsonl", {"event": "queen_started", "port": QUEEN_PORT})

    ac = get_ants_config()
    raw = ac.get("auto_spawn", True)
    auto_spawn = raw if isinstance(raw, bool) else str(raw).strip().lower() in ("1", "true", "yes")
    if auto_spawn and root_config.can_spawn_subordinates:
        spawner = DockerSpawner()
        workers = [a for a in app.state.visible_agents if a.agent_id != root_config.agent_id]
        rconf = load_runtime_config()
        runtime_env = runtime_config_to_env({k: v for k, v in rconf.items() if k not in ("ants", "nest")})
        created = spawner.ensure_children(workers, extra_env=runtime_env)
        write_log(root_config.agent_id, "runtime.jsonl", {
            "event": "queen_spawn_workers",
            "containers": created,
            "docker_available": spawner.available(),
        })

    # Register with Nest
    base_url = f"http://ants-queen:{QUEEN_PORT}"
    hb_path = await _register_with_nest(root_config, base_url)
    hb_task = None
    if hb_path:
        hb_task = asyncio.create_task(_heartbeat_loop(root_config, hb_path))
        write_log(root_config.agent_id, "runtime.jsonl", {"event": "nest_registered"})

    yield

    if hb_task:
        hb_task.cancel()


app = FastAPI(title="Ants Queen (creator_decider)", version="0.1.0", lifespan=lifespan)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _aip_send_params() -> SendParams:
    ac = get_ants_config()
    timeout = float(ac.get("aip_send_timeout") or 30)
    max_retries = int(ac.get("aip_send_max_retries") or 4)
    return SendParams(timeout=timeout, max_retries=max_retries)


def _resolve_worker_base_url(target_agent_id: str, visible_agents: list[AgentConfig], msg: AIPMessage | None = None) -> str:
    target_cfg = next((a for a in visible_agents if a.agent_id == target_agent_id), None)
    if msg and msg.to_base_url:
        return msg.to_base_url.rstrip("/")
    if target_cfg and target_cfg.status_api_base:
        return target_cfg.status_api_base.rstrip("/")
    return f"http://ants-{target_agent_id}:{WORKER_SERVICE_PORT}"


async def _forward_aip(msg: AIPMessage, target_agent_id: str, visible_agents: list[AgentConfig]) -> dict:
    base_url = _resolve_worker_base_url(target_agent_id, visible_agents, msg)
    body = msg.model_dump(by_alias=True, mode="json")
    try:
        return await async_send(base_url, body, params=_aip_send_params())
    except Exception as e:
        raise HTTPException(503, f"Agent {target_agent_id} unreachable: {e}") from e


@app.post("/aip")
@app.post("/v1/aip")
async def aip_receive(body: dict) -> dict:
    root_config: AgentConfig = app.state.root_config
    visible_agents: list[AgentConfig] = app.state.visible_agents
    try:
        msg = AIPMessage.model_validate(body)
    except Exception as e:
        raise HTTPException(422, f"Invalid AIP message: {e}") from e

    append_aip_message(root_config.agent_id, "in", msg.model_dump(by_alias=True, mode="json"))

    if msg.to != root_config.agent_id and msg.to != "*":
        return await _forward_aip(msg, msg.to, visible_agents)

    if msg.action == AIPAction.user_instruction:
        trace_id = msg.trace_id or str(uuid4())
        msg.trace_id = trace_id
        msg.correlation_id = trace_id
        payload_base = dict(msg.payload or {})
        payload_base["trace_id"] = trace_id
        msg.payload = payload_base
        instruction_text = payload_base.get("instruction", "")

        trace_log("user_instruction", trace_id=trace_id, agent_id=root_config.agent_id)

        workers = [a for a in visible_agents if a.agent_id != root_config.agent_id]
        if not workers:
            return {"ok": False, "message": "no workers available"}

        tasks = await asyncio.to_thread(decompose_instruction, instruction_text, workers)
        if tasks:
            params = _aip_send_params()
            batch_requests: list[tuple[str, dict]] = []
            for t in tasks:
                to_id = t["to"]
                payload = {**payload_base, "summary": t.get("summary", "")}
                forward_msg = AIPMessage(
                    from_agent=root_config.agent_id,
                    to=to_id,
                    action=AIPAction.assign_task,
                    intent="user_instruction",
                    payload=payload,
                    trace_id=trace_id,
                    correlation_id=trace_id,
                )
                base_url = _resolve_worker_base_url(to_id, visible_agents, forward_msg)
                batch_requests.append((base_url, forward_msg.model_dump(by_alias=True, mode="json")))
            results = await async_send_batch(batch_requests, params=params)
            for i, r in enumerate(results):
                if isinstance(r, BaseException):
                    raise HTTPException(503, f"Agent {tasks[i]['to']} unreachable: {r}") from r
            return results[-1] if results else {"ok": True, "message": "delegated"}

        first = workers[0]
        forward_msg = AIPMessage(
            from_agent=root_config.agent_id,
            to=first.agent_id,
            action=AIPAction.assign_task,
            intent="user_instruction",
            payload=payload_base,
            trace_id=trace_id,
            correlation_id=trace_id,
        )
        return await _forward_aip(forward_msg, first.agent_id, visible_agents)

    msg.status = AIPStatus.in_progress
    return {"ok": True, "message_id": msg.message_id, "to": root_config.agent_id, "status": "received"}


@app.get("/status")
@app.get("/v1/status")
async def status() -> dict:
    """Basic self status for Queen."""
    root_config: AgentConfig = app.state.root_config
    return {
        "agent_id": root_config.agent_id,
        "role": root_config.role,
        "lifecycle": "running",
        "ok": True,
    }
