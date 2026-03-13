"""Docker orchestration for Ants. Spawns workers with runtime config and Nest registration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from ants.runtime.models import AgentConfig

WORKER_SERVICE_PORT = 22001

try:
    import docker
    from docker.errors import DockerException, NotFound
except Exception:
    docker = None
    DockerException = Exception
    NotFound = Exception

_TRACE_SUBDIRS = ("workspace", "logs", "conversations", "aip", "todos", "reports", "context")


class DockerSpawner:

    def __init__(self) -> None:
        self.project_root = Path((os.getenv("ANTS_HOST_PROJECT_ROOT") or "").strip()).expanduser()
        self.project_root_local = Path("/app/host")
        self.image = (os.getenv("ANTS_IMAGE") or "ants:latest").strip()
        self.network = (os.getenv("ANTS_NETWORK") or "").strip() or None
        self.client = None
        if docker is not None:
            try:
                self.client = docker.from_env()
            except DockerException:
                self.client = None

    def available(self) -> bool:
        return self.client is not None and bool(str(self.project_root).strip())

    def child_container_name(self, agent_id: str) -> str:
        return f"ants-{agent_id}"

    def ensure_volume_dirs(self, agent_id: str) -> Path:
        root = self.project_root_local / "volumes" / agent_id
        for sub in _TRACE_SUBDIRS:
            (root / sub).mkdir(parents=True, exist_ok=True)
        for shared in ("shared/tools", "shared/inbox"):
            (self.project_root_local / shared).mkdir(parents=True, exist_ok=True)
        return self.project_root / "volumes" / agent_id

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
                "bind": "/app/config/agent.json",
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
        config_file = f"{child.agent_id}.json"
        if not (self.project_root_local / "configs" / "agents" / config_file).exists():
            return None
        volumes = self._volume_binds(child.agent_id, config_file)

        nest_url = os.getenv("NEST_URL", "http://nest:22000")
        nest_secret = os.getenv("NEST_SECRET", "")

        environment = {
            "ANT_CONFIG": "/app/config/agent.json",
            "ANT_AGENT_ID": child.agent_id,
            "ANT_BASE_DIR": f"/runtime/volumes/{child.agent_id}",
            "ANT_WORKSPACE": "/workspace",
            "ANT_SERVICE_PORT": str(WORKER_SERVICE_PORT),
            "NEST_URL": nest_url,
            "NEST_SECRET": nest_secret,
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
        if not self.available():
            return []
        created: list[str] = []
        for child in children:
            name = self.spawn_one(child, extra_env=extra_env)
            if name:
                created.append(name)
        return created
