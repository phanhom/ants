"""Nest — Agent Management Platform API.

Provides agent registry, heartbeat tracking, AIP message routing,
trace/cost observability, and a convenience instruction endpoint.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware

from aip import AIPMessage, GroupStatus, SendParams, async_send

from nest.db import init_db, write_trace, query_traces
from nest.registry import registry

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("Nest platform ready")
    yield


app = FastAPI(title="Nest — Agent Management Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Registry ─────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    agent_id: str
    base_url: str
    namespace: str = "default"
    role: str = "worker"
    superior: str | None = None
    subordinates: list[str] = []
    authority_weight: int = 50
    endpoints: dict[str, str] = {}
    tags: list[str] = []
    display_name: str | None = None


@app.post("/v1/registry/agents")
async def register_agent(body: RegisterRequest) -> dict:
    result = registry.register(body.model_dump())
    write_trace(body.agent_id, "registry", {
        "event": "registered",
        "base_url": body.base_url,
        "role": body.role,
        "namespace": body.namespace,
    })
    log.info("Agent registered: %s (%s) at %s", body.agent_id, body.role, body.base_url)
    return result


@app.post("/v1/registry/agents/{agent_id}/heartbeat")
async def receive_heartbeat(agent_id: str, body: dict) -> dict:
    ok = registry.heartbeat(agent_id, body)
    if not ok:
        raise HTTPException(404, f"Agent {agent_id} not registered")
    return {"ok": True}


@app.delete("/v1/registry/agents/{agent_id}")
async def deregister_agent(agent_id: str) -> dict:
    ok = registry.deregister(agent_id)
    if ok:
        write_trace(agent_id, "registry", {"event": "deregistered"})
        log.info("Agent deregistered: %s", agent_id)
    return {"ok": ok}


# ── Agent Discovery ──────────────────────────────────────────────────


@app.get("/v1/agents")
async def list_agents() -> list[dict]:
    agents = registry.list_agents()
    return [registry.build_agent_status(a).model_dump(mode="json") for a in agents]


@app.get("/v1/agents/{agent_id}/status")
async def agent_status(agent_id: str) -> dict:
    agent = registry.get(agent_id)
    if agent is None:
        raise HTTPException(404, f"Agent {agent_id} not found")
    return registry.build_agent_status(agent).model_dump(mode="json")


# ── Status ───────────────────────────────────────────────────────────


@app.get("/status")
@app.get("/v1/status")
async def group_status(
    scope: str = Query("group"),
    root: str | None = Query(None),
) -> dict:
    if scope in ("colony", "group"):
        return registry.build_group_status().model_dump(mode="json")
    if scope == "subtree":
        target = root or _find_root_agent_id()
        if target is None:
            raise HTTPException(404, "No agents registered")
        node = registry.build_subtree(target)
        if node is None:
            raise HTTPException(404, f"Agent {target} not found")
        return node.model_dump(mode="json")
    if scope == "self" and root:
        agent = registry.get(root)
        if agent is None:
            raise HTTPException(404, f"Agent {root} not found")
        return registry.build_agent_status(agent).model_dump(mode="json")
    return registry.build_group_status().model_dump(mode="json")


def _find_root_agent_id() -> str | None:
    for a in registry.list_agents():
        if a.superior is None:
            return a.agent_id
    agents = registry.list_agents()
    return agents[0].agent_id if agents else None


# ── AIP Message Routing ──────────────────────────────────────────────


@app.post("/v1/aip")
@app.post("/aip")
async def route_aip(body: dict) -> dict:
    """Route AIP message by 'to' field to the registered agent's base_url."""
    try:
        msg = AIPMessage.model_validate(body)
    except Exception as e:
        raise HTTPException(422, f"Invalid AIP message: {e}") from e

    write_trace(msg.from_agent or "unknown", "aip", {
        "direction": "routed",
        "from": msg.from_agent,
        "to": msg.to,
        "action": msg.action,
        "message_id": msg.message_id,
    })

    target = registry.get(msg.to)
    if target is None:
        raise HTTPException(404, f"Agent {msg.to} not registered")

    base_url = target.base_url.rstrip("/")
    aip_url = target.endpoints.get("aip", f"{base_url}/v1/aip")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(aip_url, json=body)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Agent {msg.to} unreachable: {e}") from e


@app.post("/v1/agents/{agent_id}/aip")
async def send_to_agent(agent_id: str, body: dict) -> dict:
    target = registry.get(agent_id)
    if target is None:
        raise HTTPException(404, f"Agent {agent_id} not registered")

    base_url = target.base_url.rstrip("/")
    aip_url = target.endpoints.get("aip", f"{base_url}/v1/aip")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(aip_url, json=body)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(503, f"Agent {agent_id} unreachable: {e}") from e


# ── Instruction (convenience) ────────────────────────────────────────


class InstructionRequest(BaseModel):
    instruction: str
    task_id: str | None = None


@app.post("/instruction")
async def instruction(body: InstructionRequest) -> dict:
    """Convenience: wrap instruction as AIP user_instruction and route to root agent."""
    from aip import AIPAction, AIPMessage as Msg

    root_id = _find_root_agent_id()
    if root_id is None:
        raise HTTPException(503, "No agents registered")

    msg = Msg(
        from_agent="user",
        to=root_id,
        action=AIPAction.user_instruction,
        intent="user_instruction",
        payload={"instruction": body.instruction, "task_id": body.task_id},
    )
    return await route_aip(msg.model_dump(by_alias=True, mode="json"))


# ── Traces / Observability ───────────────────────────────────────────


@app.post("/v1/traces")
async def receive_traces(body: dict | list) -> dict:
    """Receive trace events from agents."""
    events = body if isinstance(body, list) else [body]
    count = 0
    for ev in events:
        agent_id = ev.get("agent_id", "unknown")
        trace_type = ev.get("trace_type", "trace")
        if write_trace(agent_id, trace_type, ev):
            count += 1
    return {"ok": True, "accepted": count}


@app.get("/v1/traces")
async def get_traces(
    agent_id: str | None = Query(None),
    trace_type: str | None = Query(None),
    since: str | None = Query(None),
    limit: int = Query(100),
) -> list[dict]:
    return query_traces(agent_id=agent_id, trace_type=trace_type, since=since, limit=limit)


@app.get("/v1/usage")
async def get_usage(
    agent_id: str | None = Query(None),
    since: str | None = Query(None),
) -> dict:
    rows = query_traces(agent_id=agent_id, trace_type="llm_usage", since=since, limit=10000)
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0
    by_agent: dict[str, dict] = {}
    for r in rows:
        p = r.get("payload") or {}
        aid = p.get("agent_id") or r.get("agent_id", "unknown")
        pt = p.get("prompt_tokens", 0) or 0
        ct = p.get("completion_tokens", 0) or 0
        cost = p.get("estimated_cost_usd", 0) or 0
        total_prompt += pt
        total_completion += ct
        total_cost += float(cost)
        if aid not in by_agent:
            by_agent[aid] = {"prompt_tokens": 0, "completion_tokens": 0, "total_calls": 0, "cost": 0.0}
        by_agent[aid]["prompt_tokens"] += pt
        by_agent[aid]["completion_tokens"] += ct
        by_agent[aid]["total_calls"] += 1
        by_agent[aid]["cost"] += float(cost)
    return {
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_cost_usd": total_cost,
        "total_calls": len(rows),
        "by_agent": by_agent,
    }


# ── Health ───────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "agents": len(registry.list_agents())}
