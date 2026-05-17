from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalState(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    executed = "executed"
    failed = "failed"


class IncidentStatus(str, Enum):
    open = "open"
    investigating = "investigating"
    awaiting_approval = "awaiting_approval"
    resolved = "resolved"


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    blocked = "blocked"


class EventIn(BaseModel):
    service: str
    kind: str = Field(description="metric, log, deploy, trace, or event")
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utcnow)


class AgentFinding(BaseModel):
    agent: str
    finding: str
    confidence: float
    evidence: list[str] = Field(default_factory=list)


class ContextPack(BaseModel):
    context_pack_id: str
    tokens_estimated: int
    included: list[str]
    excluded: list[str] = Field(default_factory=list)


class RemediationRecommendation(BaseModel):
    action: str
    reason: str
    risk: RiskLevel
    requires_approval: bool = True
    expected_impact: str


class Approval(BaseModel):
    id: str
    incident_id: str
    action: str
    risk: RiskLevel
    reason: str
    affected_service: str
    expected_impact: str
    state: ApprovalState = ApprovalState.pending
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)


class Incident(BaseModel):
    id: str
    service: str
    severity: str
    status: IncidentStatus = IncidentStatus.open
    summary: str
    created_at: str = Field(default_factory=utcnow)
    updated_at: str = Field(default_factory=utcnow)
    timeline: list[str] = Field(default_factory=list)
    findings: list[AgentFinding] = Field(default_factory=list)
    context_pack: ContextPack | None = None
    remediation: RemediationRecommendation | None = None
    postmortem: dict[str, Any] | None = None


class SupervisorDecision(BaseModel):
    incident_id: str
    severity: str
    summary: str
    assigned_agents: list[str]
    next_action: str


class MemoryNode(BaseModel):
    id: str
    type: str
    label: str
    payload: dict[str, Any] = Field(default_factory=dict)


class MemoryEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str
