"""Status models and aggregation from config, traces, and Docker state."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ants.runtime.models import AgentConfig, AgentLifecycle
from ants.runtime.traces import get_agent_base_dir, list_recent_jsonl

try:
    import docker
    from docker.errors import DockerException, NotFound
except Exception:  # pragma: no cover - handled at runtime
    docker = None
    DockerException = Exception
    NotFound = Exception


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Ants-specific status models (not part of AIP SDK — colony runtime state)
# ---------------------------------------------------------------------------

class StatusScope(str, Enum):
    self_scope = "self"
    subtree = "subtree"
    colony = "colony"


class StatusEndpoints(BaseModel):
    aip: str | None = None
    status: str | None = None


class WorkStatusSnapshot(BaseModel):
    todos: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    recent_aip: list[dict[str, Any]] = Field(default_factory=list)
    last_seen: str | None = None
    pending_todos: int = 0


class SingleAntStatus(BaseModel):
    agent_id: str
    role: str
    superior: str | None = None
    authority_weight: int | None = None
    lifecycle: str | None = None
    port: int | None = None
    ok: bool = True
    base_url: str | None = None
    endpoints: StatusEndpoints | None = None
    pending_todos: int = 0
    recent_errors: int = 0
    waiting_for_approval: bool = False
    last_report_at: datetime | None = None
    last_aip_at: datetime | None = None
    last_seen_at: datetime | None = None
    container_name: str | None = None
    container_state: str | None = None
    work: WorkStatusSnapshot | None = None


class RecursiveStatusNode(BaseModel):
    self: SingleAntStatus
    subordinates: list["RecursiveStatusNode"] = Field(default_factory=list)


class ColonyStatusDocument(BaseModel):
    ok: bool = True
    service: str = "ants"
    port: int = 22000
    root_agent_id: str
    timestamp: datetime = Field(default_factory=_utc_now)
    topology: dict[str, list[str]] = Field(default_factory=dict)
    waiting_for_approval: bool = False
    ants: list[SingleAntStatus] = Field(default_factory=list)


RecursiveStatusNode.model_rebuild()


# ---------------------------------------------------------------------------
# Aggregation logic
# ---------------------------------------------------------------------------

QUEEN_SERVICE_PORT = 22000


def _get_status_limits():
    return {
        "todos": 100,
        "reports": 10,
        "aip": 20,
        "logs": 50,
        "worker_todos": 50,
        "worker_logs": 10,
    }


def _normalize_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    return base_url.rstrip("/")


def _build_endpoints(base_url: str | None) -> StatusEndpoints | None:
    if not base_url:
        return None
    return StatusEndpoints(aip=f"{base_url}/aip", status=f"{base_url}/status")


def _resolve_base_url(
    agent: AgentConfig,
    *,
    port: int,
    request_base_url: str | None = None,
    is_root: bool = False,
) -> str | None:
    if agent.status_api_base:
        return _normalize_base_url(agent.status_api_base)
    if request_base_url:
        return _normalize_base_url(request_base_url)
    if is_root:
        return f"http://ants-queen:{port}"
    return f"http://ants-{agent.agent_id}:{port}"


class StatusAggregator:
    """Build the single outward-facing status document."""

    def __init__(self, root_config: AgentConfig) -> None:
        self.root_config = root_config
        env_root = (os.getenv("ANTS_VOLUMES_ROOT") or "").strip()
        self.volumes_root = (
            Path(env_root)
            if env_root
            else (Path.cwd() / "volumes" if (Path.cwd() / "volumes").exists() else Path("/tmp/ants_volumes"))
        )
        self.client = None
        if docker is not None:
            try:
                self.client = docker.from_env()
            except DockerException:
                self.client = None

    def _container_state(self, agent_id: str) -> tuple[str | None, str | None]:
        if self.client is None:
            return None, None
        name = f"ants-{agent_id}"
        try:
            container = self.client.containers.get(name)
        except NotFound:
            return name, "missing"
        container.reload()
        return name, container.status

    def _derive_status(self, agent: AgentConfig, request_base_url: str | None = None) -> SingleAntStatus:
        base = self.volumes_root / agent.agent_id
        lim = _get_status_limits()
        todo_items = list_recent_jsonl(base / "todos" / "items.jsonl", limit=lim["todos"])
        report_items = list_recent_jsonl(base / "reports" / "reports.jsonl", limit=lim["reports"])
        aip_items = list_recent_jsonl(base / "aip" / "messages.jsonl", limit=lim["aip"])
        log_items = list_recent_jsonl(base / "logs" / "runtime.jsonl", limit=lim["logs"])
        container_name, container_state = self._container_state(agent.agent_id)

        waiting_for_approval = any(item.get("requires_approval") for item in todo_items) or any(
            item.get("approval_state") == "waiting_human" for item in aip_items
        )
        recent_errors = sum(1 for item in log_items if item.get("level") == "error")
        if container_state == "running":
            lifecycle = AgentLifecycle.running
        elif container_state in {"exited", "dead", "missing"}:
            lifecycle = AgentLifecycle.failed
        elif container_state:
            lifecycle = AgentLifecycle.degraded
        elif log_items:
            lifecycle = AgentLifecycle.running
        else:
            lifecycle = AgentLifecycle.idle

        is_root = agent.agent_id == self.root_config.agent_id
        from ants.runtime.docker_manager import WORKER_SERVICE_PORT
        port = QUEEN_SERVICE_PORT if is_root else WORKER_SERVICE_PORT
        base_url = _resolve_base_url(
            agent,
            port=port,
            request_base_url=request_base_url,
            is_root=is_root,
        )
        return SingleAntStatus(
            agent_id=agent.agent_id,
            role=agent.role,
            superior=agent.superior,
            authority_weight=agent.authority_weight,
            lifecycle=lifecycle.value,
            port=port,
            base_url=base_url,
            endpoints=_build_endpoints(base_url),
            pending_todos=sum(1 for item in todo_items if item.get("status") != "completed"),
            recent_errors=recent_errors,
            waiting_for_approval=waiting_for_approval,
            last_report_at=report_items[-1].get("ts") if report_items else None,
            last_aip_at=aip_items[-1].get("updated_at") if aip_items else None,
            last_seen_at=log_items[-1].get("ts") if log_items else None,
            container_name=container_name,
            container_state=container_state,
        )

    def build(self, agents: list[AgentConfig], request_base_url: str | None = None) -> ColonyStatusDocument:
        """Aggregate all visible ants into one status payload."""
        statuses = [self._derive_status(agent, request_base_url=request_base_url) for agent in agents]
        topology = {agent.agent_id: agent.subordinates for agent in agents}
        return ColonyStatusDocument(
            root_agent_id=self.root_config.agent_id,
            port=QUEEN_SERVICE_PORT,
            topology=topology,
            waiting_for_approval=any(agent.waiting_for_approval for agent in statuses),
            ants=statuses,
        )


def build_recursive_status_tree(
    root_agent_id: str,
    *,
    statuses: dict[str, SingleAntStatus],
    topology: dict[str, list[str]],
) -> RecursiveStatusNode:
    """Build a recursive subtree from flat status rows and topology."""
    children = [
        build_recursive_status_tree(child_id, statuses=statuses, topology=topology)
        for child_id in topology.get(root_agent_id, [])
        if child_id in statuses
    ]
    return RecursiveStatusNode(self=statuses[root_agent_id], subordinates=children)


def build_worker_self_status(
    config: AgentConfig,
    port: int,
    request_base_url: str | None = None,
) -> SingleAntStatus:
    """Build this ant's work info and progress from trace dirs (no Docker)."""
    base = get_agent_base_dir(config.agent_id)
    lim = _get_status_limits()
    todos = list_recent_jsonl(base / "todos" / "items.jsonl", limit=lim["worker_todos"])
    reports = list_recent_jsonl(base / "reports" / "reports.jsonl", limit=lim["reports"])
    recent_aip = list_recent_jsonl(base / "aip" / "messages.jsonl", limit=lim["aip"])
    logs = list_recent_jsonl(base / "logs" / "runtime.jsonl", limit=lim["worker_logs"])
    last_seen = logs[-1].get("ts") if logs else None
    pending_todos = sum(1 for t in todos if t.get("status") != "completed")
    base_url = _resolve_base_url(config, port=port, request_base_url=request_base_url)
    return SingleAntStatus(
        agent_id=config.agent_id,
        role=config.role,
        superior=config.superior,
        authority_weight=config.authority_weight,
        lifecycle=AgentLifecycle.running.value if logs else AgentLifecycle.idle.value,
        port=port,
        ok=True,
        base_url=base_url,
        endpoints=_build_endpoints(base_url),
        pending_todos=pending_todos,
        last_report_at=reports[-1].get("ts") if reports else None,
        last_aip_at=recent_aip[-1].get("updated_at") if recent_aip else None,
        last_seen_at=last_seen,
        work=WorkStatusSnapshot(
            todos=todos,
            reports=reports,
            recent_aip=recent_aip,
            last_seen=last_seen,
            pending_todos=pending_todos,
        ),
    )


async def build_worker_subtree_status(
    config: AgentConfig,
    *,
    agents: list[AgentConfig],
    port: int,
    request_base_url: str | None = None,
) -> RecursiveStatusNode:
    """Build recursive status for a worker and any configured subordinates."""
    from ants.runtime.docker_manager import WORKER_SERVICE_PORT

    self_status = build_worker_self_status(config, port=port, request_base_url=request_base_url)
    agents_by_id = {agent.agent_id: agent for agent in agents}
    subordinates: list[RecursiveStatusNode] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for child_id in config.subordinates:
            child = agents_by_id.get(child_id)
            if child is None:
                continue
            child_base_url = _resolve_base_url(child, port=WORKER_SERVICE_PORT)
            try:
                response = await client.get(
                    f"{child_base_url}/status",
                    params={"scope": "subtree"},
                )
                response.raise_for_status()
                subordinates.append(RecursiveStatusNode.model_validate(response.json()))
            except Exception:
                fallback = SingleAntStatus(
                    agent_id=child.agent_id,
                    role=child.role,
                    superior=child.superior,
                    authority_weight=child.authority_weight,
                    lifecycle=AgentLifecycle.failed.value,
                    ok=False,
                    port=WORKER_SERVICE_PORT,
                    base_url=child_base_url,
                    endpoints=_build_endpoints(child_base_url),
                    recent_errors=1,
                    container_state="unreachable",
                )
                subordinates.append(RecursiveStatusNode(self=fallback, subordinates=[]))
    return RecursiveStatusNode(self=self_status, subordinates=subordinates)
