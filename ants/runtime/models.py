"""Core runtime models for Ants organization, status, and AIP governance."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class AgentLifecycle(str, Enum):
    idle = "idle"
    starting = "starting"
    running = "running"
    blocked = "blocked"
    degraded = "degraded"
    failed = "failed"


class ApprovalMode(str, Enum):
    none = "none"
    human_for_production = "human_for_production"
    always = "always"


class EnvironmentPolicy(BaseModel):
    """Rules that keep test and production actions separate."""

    default_target: str = "test"
    production_requires_human_approval: bool = True
    allow_auto_apply_in_test: bool = True
    approval_mode: ApprovalMode = ApprovalMode.human_for_production


class PromptProfile(BaseModel):
    """Persistent instruction profile for each ant."""

    persona: str
    system_rules: list[str] = Field(default_factory=list)
    communication_style: str = "concise"
    escalation_style: str = "report_facts_then_blockers"


class AgentConfig(BaseModel):
    """Full employee template, designed for future role expansion."""

    agent_id: str
    display_name: str
    role: str
    superior: str | None = None
    subordinates: list[str] = Field(default_factory=list)
    rank_level: int = 1
    authority_weight: int = 50
    execution_scope: list[str] = Field(default_factory=list)
    management_scope: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools_allowed: list[str] = Field(default_factory=list)
    prompt_profile: PromptProfile
    can_spawn_subordinates: bool = False
    max_subordinates: int = 0
    environment_policy: EnvironmentPolicy = Field(default_factory=EnvironmentPolicy)
    token_ref: str | None = None
    status_api_base: str | None = None
    image: str | None = None
    tags: list[str] = Field(default_factory=list)


class AgentStatus(BaseModel):
    """Status summary exposed by the outward-facing status API."""

    agent_id: str
    role: str
    superior: str | None = None
    authority_weight: int
    lifecycle: AgentLifecycle = AgentLifecycle.idle
    pending_todos: int = 0
    recent_errors: int = 0
    waiting_for_approval: bool = False
    last_report_at: datetime | None = None
    last_aip_at: datetime | None = None
    last_seen_at: datetime | None = None
    container_name: str | None = None
    container_state: str | None = None


class StatusEnvelope(BaseModel):
    """Single outward-facing status document."""

    ok: bool = True
    service: str = "ants"
    port: int = 22000
    root_agent_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    topology: dict[str, list[str]] = Field(default_factory=dict)
    waiting_for_approval: bool = False
    ants: list[AgentStatus] = Field(default_factory=list)
