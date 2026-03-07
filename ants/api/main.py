"""Ants API: 蚁后 (queen) — status and AIP conversation. User = 老板的上级."""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel

from ants.protocol.aip import AIPAction, AIPMessage, AIPStatus
from ants.protocol.status import StatusScope
from ants.runtime.config import (
    get_config_dir,
    list_available_agent_ids,
    load_agent_config,
    load_all_agent_configs,
)
from ants.runtime.docker_manager import DockerSpawner, WORKER_SERVICE_PORT
from ants.runtime.models import AgentConfig
from ants.runtime.runtime_config import load_runtime_config, runtime_config_to_env
from ants.runtime.status import StatusAggregator, build_recursive_status_tree
from ants.runtime.traces import append_aip_message, ensure_trace_dirs, write_log


def _admin_token() -> str | None:
    return os.getenv("ANT_ADMIN_TOKEN") or os.getenv("ANTS_ADMIN_TOKEN")


def require_admin(x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> None:
    """Dependency: require admin token for internal endpoints (二把手)."""
    token = _admin_token()
    if not token:
        raise HTTPException(501, "Admin token not configured")
    if x_admin_token != token:
        raise HTTPException(403, "Invalid or missing admin token")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """蚁后 (queen) boot: ensure traces; spawn all workers from config (except self)."""
    config_dir = get_config_dir()
    root_path = config_dir / "creator_decider.yaml"
    if not root_path.exists():
        raise FileNotFoundError(
            f"Root config not found: {root_path}. Set ANTS_CONFIG_DIR or run from repo root."
        )
    root_config = load_agent_config(root_path)
    ensure_trace_dirs(root_config.agent_id)
    app.state.root_config = root_config
    app.state.config_dir = config_dir
    app.state.visible_agents = load_all_agent_configs(config_dir)
    write_log(root_config.agent_id, "runtime.jsonl", {"event": "queen_started", "port": 22000})

    auto_spawn = os.getenv("ANTS_AUTO_SPAWN_DEFAULT", "1").strip().lower() in ("1", "true", "yes")
    if auto_spawn and root_config.can_spawn_subordinates:
        spawner = DockerSpawner()
        workers = [a for a in app.state.visible_agents if a.agent_id != root_config.agent_id]
        rconf = load_runtime_config()
        runtime_env = runtime_config_to_env(rconf)
        queen_url = (rconf.get("queen") or {}).get("base_url") or os.getenv("ANTS_QUEEN_URL")
        if queen_url:
            runtime_env["ANT_QUEEN_URL"] = queen_url.rstrip("/")
        created = spawner.ensure_children(workers, extra_env=runtime_env)
        write_log(
            root_config.agent_id,
            "runtime.jsonl",
            {"event": "queen_spawn_workers", "containers": created, "docker_available": spawner.available()},
        )
    yield


app = FastAPI(title="Ants 蚁后 (queen)", version="0.1.0", lifespan=lifespan)


def _request_base_url(request: Request) -> str:
    """Return this request's base URL without a trailing slash."""
    return str(request.base_url).rstrip("/")


# ---------- Interface 1: Status / work info (aggregate for colony) ----------

@app.get("/status")
async def status(
    request: Request,
    scope: StatusScope = Query(StatusScope.colony),
    root: str | None = Query(None),
) -> dict:
    """Return colony, self, or subtree status for the queen topology."""
    root_config: AgentConfig = app.state.root_config
    visible_agents: list[AgentConfig] = app.state.visible_agents
    aggregator = StatusAggregator(root_config)
    colony = aggregator.build(visible_agents, request_base_url=_request_base_url(request))

    if scope == StatusScope.self_scope:
        root_status = next((item for item in colony.ants if item.agent_id == root_config.agent_id), None)
        if root_status is None:
            raise HTTPException(404, "Root agent status not found")
        return root_status.model_dump(mode="json")

    if scope == StatusScope.subtree:
        target_root = root or root_config.agent_id
        statuses = {item.agent_id: item for item in colony.ants}
        if target_root not in statuses:
            raise HTTPException(404, f"Unknown root agent_id: {target_root}")
        subtree = build_recursive_status_tree(target_root, statuses=statuses, topology=colony.topology)
        return subtree.model_dump(mode="json")

    return colony.model_dump(mode="json")


# ---------- Interface 2: Container-to-container conversation (AIP); supports cross-server ----------

async def _forward_aip(msg: AIPMessage, target_agent_id: str, visible_agents: list[AgentConfig]) -> dict:
    """Forward AIP to local worker or remote (to_base_url)."""
    target_cfg = next((a for a in visible_agents if a.agent_id == target_agent_id), None)
    base_url = None
    if msg.to_base_url:
        base_url = msg.to_base_url.rstrip("/")
    elif target_cfg and target_cfg.status_api_base:
        base_url = target_cfg.status_api_base.rstrip("/")
    if not base_url:
        base_url = f"http://ants-{target_agent_id}:{WORKER_SERVICE_PORT}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(f"{base_url}/aip", json=msg.to_wire())
            r.raise_for_status()
            return r.json()
    except Exception as e:
        raise HTTPException(503, f"Ant {target_agent_id} unreachable: {e}") from e


def _decompose_instruction_sync(instruction: str, workers: list[AgentConfig]) -> list[dict] | None:
    """
    Call LLM to split instruction into per-worker tasks. Returns list of { to, summary } or None on failure.
    Uses runtime llm config (same as workers).
    """
    rconf = load_runtime_config()
    llm = rconf.get("llm") or {}
    base_url = (llm.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = llm.get("model_name") or "gpt-4"
    api_key = llm.get("api_key") or os.getenv("LLM_API_KEY", "")
    if not api_key:
        return None
    workers_json = json.dumps(
        [{"agent_id": w.agent_id, "role": w.role, "skills": w.skills[:15]} for w in workers],
        ensure_ascii=False,
    )
    user_content = (
        f"Decompose the user instruction into one or more tasks, each for a specific worker. "
        f"Output a JSON array only. Each item: {{ \"to\": \"<agent_id>\", \"summary\": \"<short task for that worker>\" }}. "
        f"Use only agent_id from the workers list. One task per worker at most.\n\n"
        f"User instruction: {instruction}\n\nWorkers: {workers_json}"
    )
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You output only a valid JSON array. No markdown, no explanation."},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 1500,
                },
            )
            if r.status_code != 200:
                return None
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    except Exception:
        return None
    content = content.strip()
    for prefix in ("```json", "```"):
        if content.startswith(prefix):
            content = content[len(prefix) :].strip()
        if content.endswith("```"):
            content = content[:-3].strip()
    try:
        tasks = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(tasks, list) or not tasks:
        return None
    valid_ids = {w.agent_id for w in workers}
    out = []
    for t in tasks:
        if not isinstance(t, dict):
            continue
        to_id = t.get("to")
        summary = t.get("summary") or ""
        if to_id in valid_ids and summary:
            out.append({"to": to_id, "summary": summary})
    return out if out else None


@app.post("/aip")
async def aip_receive(body: dict) -> dict:
    """
    Receive AIP message from any ant or user. Same-host or cross-server (use to_base_url).
    Queen persists, then routes: if to != self, forward to that ant's /aip (local or remote).
    """
    root_config: AgentConfig = app.state.root_config
    visible_agents: list[AgentConfig] = app.state.visible_agents
    try:
        msg = AIPMessage.model_validate(body)
    except Exception as e:
        raise HTTPException(422, f"Invalid AIP message: {e}") from e

    append_aip_message(root_config.agent_id, "in", msg.to_wire())

    if msg.to != root_config.agent_id and msg.to != "*":
        out = await _forward_aip(msg, msg.to, visible_agents)
        write_log(
            root_config.agent_id,
            "runtime.jsonl",
            {"event": "aip_forwarded", "to": msg.to, "message_id": msg.message_id},
        )
        return out

    if msg.action == AIPAction.user_instruction:
        workers = [a for a in visible_agents if a.agent_id != root_config.agent_id]
        if not workers:
            return {"ok": False, "message": "no workers available"}
        instruction_text = (msg.payload or {}).get("instruction", "")
        tasks = await asyncio.to_thread(_decompose_instruction_sync, instruction_text, workers)
        if tasks:
            last_out = None
            for t in tasks:
                to_id = t["to"]
                summary = t.get("summary", "")
                payload = {**(msg.payload or {}), "summary": summary}
                forward_msg = AIPMessage(
                    from_ant=root_config.agent_id,
                    to=to_id,
                    action=AIPAction.assign_task,
                    intent="user_instruction",
                    payload=payload,
                )
                last_out = await _forward_aip(forward_msg, to_id, visible_agents)
            return last_out or {"ok": True, "message": "delegated"}
        first = workers[0]
        forward_msg = AIPMessage(
            from_ant=root_config.agent_id,
            to=first.agent_id,
            action=AIPAction.assign_task,
            intent="user_instruction",
            payload=msg.payload,
        )
        return await _forward_aip(forward_msg, first.agent_id, visible_agents)

    msg.touch(AIPStatus.in_progress)
    return {"ok": True, "message_id": msg.message_id, "to": root_config.agent_id, "status": "received"}


# ---------- Convenience: user instruction as AIP ----------

class InstructionRequest(BaseModel):
    instruction: str
    task_id: str | None = None


@app.post("/instruction")
async def instruction(body: InstructionRequest) -> dict:
    """Convenience: user instruction as AIP user_instruction to queen (then delegated to worker)."""
    root_config: AgentConfig = app.state.root_config
    msg = AIPMessage(
        from_ant="user",
        to=root_config.agent_id,
        action=AIPAction.user_instruction,
        intent="user_instruction",
        payload={"instruction": body.instruction, "task_id": body.task_id},
    )
    return await aip_receive(msg.to_wire())


# ---------- Internal (admin): list configs, dynamic spawn ----------

@app.get("/internal/configs")
async def internal_list_configs(_: None = Depends(require_admin)) -> dict:
    """List available employee configs (templates)."""
    config_dir: Path = app.state.config_dir
    return {"agent_ids": list_available_agent_ids(config_dir)}


class SpawnRequest(BaseModel):
    agent_id: str


@app.post("/internal/spawn")
async def internal_spawn(
    body: SpawnRequest,
    _: None = Depends(require_admin),
) -> dict:
    """Create one worker container from config. Injects runtime env."""
    config_dir: Path = app.state.config_dir
    path = config_dir / f"{body.agent_id}.yaml"
    if not path.exists():
        raise HTTPException(404, f"No config for agent_id: {body.agent_id}")
    cfg = load_agent_config(path)
    spawner = DockerSpawner()
    runtime_env = runtime_config_to_env(load_runtime_config())
    name = spawner.spawn_one(cfg, extra_env=runtime_env)
    if name is None:
        raise HTTPException(503, "Docker unavailable or spawn failed")
    write_log(
        app.state.root_config.agent_id,
        "runtime.jsonl",
        {"event": "dynamic_spawn", "agent_id": body.agent_id, "container": name},
    )
    return {"ok": True, "agent_id": body.agent_id, "container": name}
