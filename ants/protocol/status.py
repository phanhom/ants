"""Protocol-level status models for Ants. Safe to export as a library surface."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class StatusScope(str, Enum):
    """Supported status query scopes."""

    self_scope = "self"
    subtree = "subtree"
    colony = "colony"


class StatusEndpoints(BaseModel):
    """Public endpoints that can be discovered from a status response."""

    aip: str | None = None
    status: str | None = None


class WorkStatusSnapshot(BaseModel):
    """Work-in-progress snapshot for one ant."""

    todos: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    recent_aip: list[dict[str, Any]] = Field(default_factory=list)
    last_seen: str | None = None
    pending_todos: int = 0


class SingleAntStatus(BaseModel):
    """One ant's status document, usable for workers and aggregate views."""

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
    """Recursive status tree: current ant plus all direct and indirect subordinates."""

    self: SingleAntStatus
    subordinates: list["RecursiveStatusNode"] = Field(default_factory=list)


class ColonyStatusDocument(BaseModel):
    """Flat colony-wide status document, optimized for dashboards and summaries."""

    ok: bool = True
    service: str = "ants"
    port: int = 22000
    root_agent_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    topology: dict[str, list[str]] = Field(default_factory=dict)
    waiting_for_approval: bool = False
    ants: list[SingleAntStatus] = Field(default_factory=list)


RecursiveStatusNode.model_rebuild()
