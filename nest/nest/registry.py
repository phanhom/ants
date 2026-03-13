"""In-memory agent registry with heartbeat-based lifecycle tracking."""

from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from aip import AgentStatus, GroupStatus, StatusEndpoints, RecursiveStatusNode

from nest.config import get_registry_config


@dataclass
class RegisteredAgent:
    agent_id: str
    base_url: str
    namespace: str = "default"
    role: str = "worker"
    superior: str | None = None
    subordinates: list[str] = field(default_factory=list)
    authority_weight: int = 50
    endpoints: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    display_name: str | None = None
    # heartbeat state
    ok: bool = True
    lifecycle: str = "running"
    pending_tasks: int = 0
    last_heartbeat: float = field(default_factory=time.monotonic)
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AgentRegistry:
    """Thread-safe agent registry. Agents register, send heartbeats, and can be queried."""

    def __init__(self) -> None:
        self._agents: dict[str, RegisteredAgent] = {}
        self._lock = threading.Lock()

    @property
    def _heartbeat_timeout(self) -> float:
        return float(get_registry_config().get("heartbeat_timeout") or 30)

    @property
    def _heartbeat_dead(self) -> float:
        return float(get_registry_config().get("heartbeat_dead") or 120)

    def register(self, data: dict[str, Any]) -> dict[str, str]:
        agent_id = data["agent_id"]
        agent = RegisteredAgent(
            agent_id=agent_id,
            base_url=data.get("base_url", ""),
            namespace=data.get("namespace", "default"),
            role=data.get("role", "worker"),
            superior=data.get("superior"),
            subordinates=data.get("subordinates") or [],
            authority_weight=data.get("authority_weight", 50),
            endpoints=data.get("endpoints") or {},
            tags=data.get("tags") or [],
            display_name=data.get("display_name"),
        )
        with self._lock:
            self._agents[agent_id] = agent
        return {"heartbeat_url": f"/v1/registry/agents/{agent_id}/heartbeat"}

    def heartbeat(self, agent_id: str, data: dict[str, Any]) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            agent.ok = data.get("ok", True)
            agent.lifecycle = data.get("lifecycle", "running")
            agent.pending_tasks = data.get("pending_tasks", 0)
            agent.last_heartbeat = time.monotonic()
            return True

    def deregister(self, agent_id: str) -> bool:
        with self._lock:
            return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> RegisteredAgent | None:
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(self) -> list[RegisteredAgent]:
        with self._lock:
            return list(self._agents.values())

    def _effective_lifecycle(self, agent: RegisteredAgent) -> str:
        elapsed = time.monotonic() - agent.last_heartbeat
        if elapsed > self._heartbeat_dead:
            return "failed"
        if elapsed > self._heartbeat_timeout:
            return "degraded"
        return agent.lifecycle

    def build_agent_status(self, agent: RegisteredAgent) -> AgentStatus:
        lifecycle = self._effective_lifecycle(agent)
        endpoints = StatusEndpoints(
            aip=agent.endpoints.get("aip", f"{agent.base_url}/v1/aip"),
            status=agent.endpoints.get("status", f"{agent.base_url}/v1/status"),
        ) if agent.base_url else None
        return AgentStatus(
            agent_id=agent.agent_id,
            role=agent.role,
            namespace=agent.namespace,
            superior=agent.superior,
            authority_weight=agent.authority_weight,
            lifecycle=lifecycle,
            port=None,
            ok=agent.ok and lifecycle not in ("failed",),
            base_url=agent.base_url,
            endpoints=endpoints,
            pending_tasks=agent.pending_tasks,
            last_seen_at=datetime.fromtimestamp(
                time.time() - (time.monotonic() - agent.last_heartbeat), tz=timezone.utc
            ).isoformat(),
            metadata={
                "registered_at": agent.registered_at,
                "display_name": agent.display_name,
                "tags": agent.tags,
            },
        )

    def build_group_status(self) -> GroupStatus:
        agents = self.list_agents()
        statuses = [self.build_agent_status(a) for a in agents]
        topology: dict[str, list[str]] = {}
        for a in agents:
            topology[a.agent_id] = a.subordinates
        root_id = None
        for a in agents:
            if a.superior is None:
                root_id = a.agent_id
                break
        return GroupStatus(
            root_agent_id=root_id,
            topology=topology,
            waiting_for_approval=False,
            agents=statuses,
        )

    def build_subtree(self, root_id: str) -> RecursiveStatusNode | None:
        agents_map = {a.agent_id: a for a in self.list_agents()}
        if root_id not in agents_map:
            return None
        return self._build_node(root_id, agents_map)

    def _build_node(self, agent_id: str, agents_map: dict[str, RegisteredAgent]) -> RecursiveStatusNode:
        agent = agents_map[agent_id]
        status = self.build_agent_status(agent)
        children = [
            self._build_node(cid, agents_map)
            for cid in agent.subordinates
            if cid in agents_map
        ]
        return RecursiveStatusNode(self=status, subordinates=children)


registry = AgentRegistry()
