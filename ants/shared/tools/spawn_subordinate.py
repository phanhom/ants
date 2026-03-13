"""Create or ensure subordinate worker containers. Only for root ant with can_spawn_subordinates."""

import os

TOOL_NAME = "spawn_subordinate"
TOOL_DESCRIPTION = (
    "Create or start direct subordinate worker containers. "
    "Only allowed for the root ant (creator_decider) with can_spawn_subordinates. "
    "Optional agent_id: ensure that specific subordinate is running."
)
TOOL_PARAMS = {
    "type": "object",
    "properties": {
        "agent_id": {"type": "string", "description": "Optional: specific subordinate agent_id to ensure running. Omit to ensure all configured subordinates."},
    },
    "required": [],
}


def run(agent_id: str | None = None) -> str:
    try:
        from ants.runtime.config import load_agent_config
        from ants.runtime.docker_manager import DockerSpawner
        from ants.runtime.models import AgentConfig
        from ants.agents.bootstrap import load_child_configs, spawn_subordinates
    except ImportError as e:
        return f"Error: {e}"
    config = load_agent_config()
    if not getattr(config, "can_spawn_subordinates", False):
        return "Not allowed: this ant cannot spawn subordinates."
    if agent_id:
        # Ensure single child by id (requires full config dir mounted, e.g. ANTS_CONFIG_DIR)
        from pathlib import Path
        from ants.runtime.config import get_config_dir
        config_dir = get_config_dir()
        child_path = config_dir / f"{agent_id}.json"
        if not child_path.exists():
            return f"Error: no config for subordinate {agent_id}"
        child_config = load_agent_config(child_path)
        if child_config.agent_id not in (config.subordinates or []):
            return f"Error: {agent_id} is not a configured subordinate of this ant."
        spawner = DockerSpawner()
        if not spawner.available():
            return "Error: Docker not available"
        created = spawner.ensure_children([child_config])
        return f"Spawned/ensured subordinate: {agent_id}; created: {created}"
    # Ensure all configured subordinates
    created = spawn_subordinates(config)
    subs = getattr(config, "subordinates", []) or []
    return f"Spawned/ensured subordinates: {', '.join(subs)}; containers created: {created}"
