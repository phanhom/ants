"""Load Ant configuration files. Configs are templates; runtime spawns from them."""

from __future__ import annotations

import json
import os
from pathlib import Path

from ants.runtime.models import AgentConfig


def get_config_dir() -> Path:
    """Config dir: env ANTS_CONFIG_DIR or default cwd/configs/agents, /app/configs/agents."""
    path = (os.getenv("ANTS_CONFIG_DIR") or "").strip()
    if path:
        return Path(path)
    cwd_agents = Path.cwd() / "configs" / "agents"
    if cwd_agents.is_dir():
        return cwd_agents
    return Path("/app/configs/agents")


def get_config_path() -> Path:
    """Resolve the active agent config file (for this process)."""
    explicit = os.getenv("ANT_CONFIG")
    if explicit:
        return Path(explicit)
    return get_config_dir() / "creator_decider.json"


def load_agent_config(path: str | Path | None = None) -> AgentConfig:
    """Load a JSON config into the shared AgentConfig model."""
    config_path = Path(path) if path else get_config_path()
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config not found: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8")) or {}
    return AgentConfig.model_validate(payload)


def list_available_agent_ids(config_dir: Path | None = None) -> list[str]:
    """List agent_ids from JSON configs in config dir (employee templates)."""
    directory = config_dir or get_config_dir()
    if not directory.is_dir():
        return []
    return [p.stem for p in directory.glob("*.json") if p.stem and not p.name.startswith(".")]


def load_all_agent_configs(config_dir: Path | None = None) -> list[AgentConfig]:
    """Load all agent configs from the config dir. Order: creator_decider first, then rest."""
    directory = config_dir or get_config_dir()
    ids = list_available_agent_ids(directory)
    configs: list[AgentConfig] = []
    root_id = "creator_decider"
    if root_id in ids:
        configs.append(load_agent_config(directory / f"{root_id}.json"))
    for aid in ids:
        if aid == root_id:
            continue
        configs.append(load_agent_config(directory / f"{aid}.json"))
    return configs
