"""Docker orchestration for 蚁后 (queen). Spawns workers with runtime config and exposed port."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ants.runtime.models import AgentConfig

WORKER_SERVICE_PORT = 22001

try:
    import docker
    from docker.errors import DockerException, NotFound
except Exception:  # pragma: no cover - handled at runtime
    docker = None
    DockerException = Exception
    NotFound = Exception

_TRACE_SUBDIRS = ("workspace", "logs", "conversations", "aip", "todos", "reports", "context")


class DockerSpawner:
    """Create child ant containers idempotently. Used at startup or by 二把手 dynamically."""

    def __init__(self) -> None:
        self.project_root = Path(os.getenv("ANTS_HOST_PROJECT_ROOT", "")).expanduser()
        self.image = os.getenv("ANTS_IMAGE", "ants:latest")
        self.network = os.getenv("ANTS_NETWORK")
        self.client = None
        if docker is not None:
            try:
                self.client = docker.from_env()
            except DockerException:
                self.client = None

    def available(self) -> bool:
        """Whether Docker is reachable and project root is set."""
        return self.client is not None and self.project_root.exists()

    def child_container_name(self, agent_id: str) -> str:
        """Stable container naming for idempotent restarts."""
        return f"ants-{agent_id}"

    def ensure_volume_dirs(self, agent_id: str) -> Path:
        """Create per-ant volume subdirs on host so binds work. Returns ant volume root."""
        root = self.project_root / "volumes" / agent_id
        for sub in _TRACE_SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
        for shared in ("shared/tools", "shared/inbox"):
            (self.project_root / shared).mkdir(parents=True, exist_ok=True)
        return root

    def _volume_binds(self, agent_id: str, config_name: str) -> dict[str, dict[str, str]]:
        base = self.project_root
        ant_root = base / "volumes" / agent_id
        binds = {
            str(ant_root / "workspace"): {"bind": "/workspace", "mode": "rw"},
            str(ant_root / "logs"): {"bind": "/logs", "mode": "rw"},
            str(ant_root / "conversations"): {"bind": "/conversations", "mode": "rw"},
            str(ant_root / "aip"): {"bind": "/aip", "mode": "rw"},
            str(ant_root / "todos"): {"bind": "/todos", "mode": "rw"},
            str(ant_root / "reports"): {"bind": "/reports", "mode": "rw"},
            str(ant_root / "context"): {"bind": "/context", "mode": "rw"},
            str(base / "shared" / "tools"): {"bind": "/shared/tools", "mode": "rw"},
            str(base / "shared" / "inbox"): {"bind": "/shared/inbox", "mode": "rw"},
            str(base / "volumes"): {"bind": "/runtime/volumes", "mode": "rw"},
            str(base / "configs" / "agents" / config_name): {
                "bind": "/app/config/agent.yaml",
                "mode": "ro",
            },
        }
        return binds

    def spawn_one(
        self,
        child: AgentConfig,
        extra_env: dict[str, str] | None = None,
        command: list[str] | None = None,
    ) -> str | None:
        """Create or start a single worker container. Injects runtime config env and exposes worker port."""
        if not self.available():
            return None
        assert self.client is not None
        name = self.child_container_name(child.agent_id)
        try:
            container = self.client.containers.get(name)
            if container.status != "running":
                container.start()
            return name
        except NotFound:
            pass

        self.ensure_volume_dirs(child.agent_id)
        config_file = f"{child.agent_id}.yaml"
        if not (self.project_root / "configs" / "agents" / config_file).exists():
            return None
        volumes = self._volume_binds(child.agent_id, config_file)
        queen_url = os.getenv("ANTS_QUEEN_URL", "http://host.docker.internal:22000")
        environment = {
            "ANT_CONFIG": "/app/config/agent.yaml",
            "ANT_AGENT_ID": child.agent_id,
            "ANT_BASE_DIR": f"/runtime/volumes/{child.agent_id}",
            "ANT_WORKSPACE": "/workspace",
            "ANT_QUEEN_URL": queen_url,
            "ANT_SERVICE_PORT": str(WORKER_SERVICE_PORT),
        }
        if extra_env:
            environment.update(extra_env)
        labels = {
            "ants.agent_id": child.agent_id,
            "ants.role": child.role,
            "ants.superior": child.superior or "",
        }
        if command is None:
            command = ["python", "-m", "ants.agents.server"]
        kwargs = {
            "image": child.image or self.image,
            "name": name,
            "command": command,
            "detach": True,
            "volumes": volumes,
            "environment": environment,
            "labels": labels,
            "restart_policy": {"Name": "unless-stopped"},
        }
        if self.network:
            kwargs["network"] = self.network
        self.client.containers.run(**kwargs)
        return name

    def ensure_children(
        self,
        children: Iterable[AgentConfig],
        extra_env: dict[str, str] | None = None,
    ) -> list[str]:
        """Create or start worker containers. Pass extra_env (e.g. runtime config) to inject into all."""
        if not self.available():
            return []
        created: list[str] = []
        for child in children:
            name = self.spawn_one(child, extra_env=extra_env)
            if name:
                created.append(name)
        return created
