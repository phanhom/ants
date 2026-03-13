"""Ant bootstrap: hot-load tools, register with Nest, heartbeat, spawn subordinates if root."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
import threading
from pathlib import Path

from ants.runtime.config import load_agent_config
from ants.runtime.docker_manager import DockerSpawner
from ants.runtime.models import AgentConfig
from ants.runtime.traces import append_jsonl, ensure_trace_dirs, utc_now_iso, write_log

SHARED_TOOLS = Path("/shared/tools")
POLL_INTERVAL = 5.0
CONFIG_DIR = Path("/app/config")
WORKER_PORT = 22001


def _load_tool_module(path: Path) -> str | None:
    if path.suffix != ".py" or path.name.startswith("_"):
        return None
    name = f"ants_tools_{path.stem}"
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return name
    except Exception as exc:
        print(f"[bootstrap] failed to load {path.name}: {exc}")
    return None


def discover_tools() -> dict[str, Path]:
    tools: dict[str, Path] = {}
    if not SHARED_TOOLS.is_dir():
        return tools
    for path in SHARED_TOOLS.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        name = _load_tool_module(path)
        if name:
            tools[name] = path
    return tools


def load_child_configs(root_config: AgentConfig) -> list[AgentConfig]:
    children: list[AgentConfig] = []
    for agent_id in root_config.subordinates[: root_config.max_subordinates]:
        config_path = CONFIG_DIR / f"{agent_id}.json"
        if not config_path.exists():
            continue
        children.append(load_agent_config(config_path))
    return children


def spawn_subordinates(root_config: AgentConfig) -> list[str]:
    if not root_config.can_spawn_subordinates:
        return []
    spawner = DockerSpawner()
    children = load_child_configs(root_config)
    created = spawner.ensure_children(children)
    write_log(root_config.agent_id, "runtime.jsonl", {
        "event": "spawn_subordinates",
        "children": [child.agent_id for child in children],
        "containers": created,
        "docker_available": spawner.available(),
    })
    return created


def write_skill_snapshot(config: AgentConfig, tool_names: list[str]) -> None:
    base = ensure_trace_dirs(config.agent_id)
    payload = {
        "ts": utc_now_iso(),
        "agent_id": config.agent_id,
        "skills": config.skills,
        "tools_allowed": config.tools_allowed,
        "hot_loaded_tools": tool_names,
    }
    append_jsonl(base / "context" / "skills.jsonl", payload)


def _nest_url() -> str:
    return (os.getenv("NEST_URL") or "").strip()


def _register_with_nest(config: AgentConfig) -> str | None:
    """Register this worker with Nest. Returns heartbeat path or None."""
    nest = _nest_url()
    if not nest:
        return None
    import httpx
    import socket
    hostname = socket.gethostname()
    base_url = f"http://ants-{config.agent_id}:{WORKER_PORT}"
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
    delay = 1.0
    max_delay = 60.0
    for _ in range(20):
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(f"{nest}/v1/registry/agents", json=body, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                write_log(config.agent_id, "runtime.jsonl", {"event": "nest_registered"})
                return data.get("heartbeat_url")
        except Exception as e:
            write_log(config.agent_id, "runtime.jsonl", {"event": "nest_register_retry", "error": str(e)})
            time.sleep(delay)
            delay = min(delay * 2, max_delay)
    return None


def _send_heartbeat(config: AgentConfig, heartbeat_path: str) -> None:
    """Send one heartbeat to Nest."""
    nest = _nest_url()
    if not nest:
        return
    import httpx
    from datetime import datetime, timezone
    url = f"{nest}{heartbeat_path}"
    secret = (os.getenv("NEST_SECRET") or "").strip()
    headers = {"Authorization": f"Bearer {secret}"} if secret else {}
    try:
        with httpx.Client(timeout=5, headers=headers) as client:
            client.post(url, json={
                "ok": True,
                "lifecycle": "running",
                "pending_tasks": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
    except Exception:
        pass


def run_bootstrap(poll: bool = True) -> None:
    config = load_agent_config()
    ensure_trace_dirs(config.agent_id)
    write_log(config.agent_id, "runtime.jsonl", {
        "event": "bootstrap_started",
        "role": config.role,
        "superior": config.superior,
    })

    tools = discover_tools()
    write_skill_snapshot(config, list(tools.keys()))
    print(f"[bootstrap] {config.agent_id} loaded {len(tools)} tools: {list(tools.keys())}")

    if config.can_spawn_subordinates:
        spawn_subordinates(config)

    heartbeat_path = _register_with_nest(config)

    if not poll:
        return

    last_mtimes: dict[Path, float] = {}
    while True:
        time.sleep(POLL_INTERVAL)

        if heartbeat_path:
            _send_heartbeat(config, heartbeat_path)

        write_log(config.agent_id, "runtime.jsonl", {
            "ts": utc_now_iso(),
            "event": "heartbeat",
            "agent_id": config.agent_id,
            "role": config.role,
        })

        if not SHARED_TOOLS.is_dir():
            continue
        for path in SHARED_TOOLS.rglob("*.py"):
            if path.name.startswith("_"):
                continue
            mtime = path.stat().st_mtime
            if last_mtimes.get(path) == mtime:
                continue
            last_mtimes[path] = mtime
            name = _load_tool_module(path)
            if name:
                write_log(config.agent_id, "runtime.jsonl", {
                    "event": "hot_loaded_tool",
                    "tool_name": name,
                    "path": str(path),
                })


if __name__ == "__main__":
    run_bootstrap(poll=True)
