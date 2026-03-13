"""Ant bootstrap: hot-load tools, persist traces, and spawn subordinates if root."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

from ants.runtime.config import load_agent_config
from ants.runtime.docker_manager import DockerSpawner
from ants.runtime.models import AgentConfig
from ants.runtime.traces import append_jsonl, ensure_trace_dirs, utc_now_iso, write_log

SHARED_TOOLS = Path("/shared/tools")
POLL_INTERVAL = 5.0
CONFIG_DIR = Path("/app/config")


def _load_tool_module(path: Path) -> str | None:
    """Load or reload a shared tool file as a Python module."""
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
    """Scan `/shared/tools` and load all public `.py` modules."""
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
    """Load only the configured direct subordinates for the root ant."""
    children: list[AgentConfig] = []
    for agent_id in root_config.subordinates[: root_config.max_subordinates]:
        config_path = CONFIG_DIR / f"{agent_id}.json"
        if not config_path.exists():
            continue
        children.append(load_agent_config(config_path))
    return children


def spawn_subordinates(root_config: AgentConfig) -> list[str]:
    """Create or start fixed child containers for the root ant."""
    if not root_config.can_spawn_subordinates:
        return []
    spawner = DockerSpawner()
    children = load_child_configs(root_config)
    created = spawner.ensure_children(children)
    write_log(
        root_config.agent_id,
        "runtime.jsonl",
        {
            "event": "spawn_subordinates",
            "children": [child.agent_id for child in children],
            "containers": created,
            "docker_available": spawner.available(),
        },
    )
    return created


def write_skill_snapshot(config: AgentConfig, tool_names: list[str]) -> None:
    """Persist the current skills and tool registry for the ant."""
    base = ensure_trace_dirs(config.agent_id)
    payload = {
        "ts": utc_now_iso(),
        "agent_id": config.agent_id,
        "skills": config.skills,
        "tools_allowed": config.tools_allowed,
        "hot_loaded_tools": tool_names,
    }
    append_jsonl(base / "context" / "skills.jsonl", payload)


def run_bootstrap(poll: bool = True) -> None:
    """Start an ant worker process and optionally keep hot-loading shared tools."""
    config = load_agent_config()
    ensure_trace_dirs(config.agent_id)
    write_log(
        config.agent_id,
        "runtime.jsonl",
        {"event": "bootstrap_started", "role": config.role, "superior": config.superior},
    )

    tools = discover_tools()
    write_skill_snapshot(config, list(tools.keys()))
    print(f"[bootstrap] {config.agent_id} loaded {len(tools)} tools: {list(tools.keys())}")

    if config.can_spawn_subordinates:
        spawn_subordinates(config)

    if not poll:
        return

    last_mtimes: dict[Path, float] = {}
    while True:
        time.sleep(POLL_INTERVAL)
        heartbeat = {
            "ts": utc_now_iso(),
            "event": "heartbeat",
            "agent_id": config.agent_id,
            "role": config.role,
        }
        print(json.dumps(heartbeat, ensure_ascii=True))
        write_log(config.agent_id, "runtime.jsonl", heartbeat)

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
                write_log(
                    config.agent_id,
                    "runtime.jsonl",
                    {"event": "hot_loaded_tool", "tool_name": name, "path": str(path)},
                )


if __name__ == "__main__":
    run_bootstrap(poll=True)
