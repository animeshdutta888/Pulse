from __future__ import annotations

import uuid
import time

from pulse.agents.specialists import (
    run_context_agent,
    run_logs_agent,
    run_metrics_agent,
    run_remediation_agent,
    run_risk_agent,
)
from pulse.context.engine import build_context_pack, retrieve_similar_incidents
from pulse.models import Approval, Incident, IncidentStatus, RiskLevel, SupervisorDecision
from pulse.store import create_approval, get_incident, list_events, update_incident
from pulse.orchestration.chaos import SCENARIOS, invoke


def investigate_incident(incident_id: str, chaos: str | None = None) -> tuple[Incident, Approval | None, SupervisorDecision]:
    incident = get_incident(incident_id)
    if not incident:
        raise ValueError(f"Unknown incident {incident_id}")

    incident.status = IncidentStatus.investigating
    started = time.perf_counter()
    trace: list[dict] = []
    incident.chaos = {"enabled": bool(chaos), "scenario": chaos, "label": SCENARIOS.get(chaos, "Normal mode")}
    events = list_events(incident.service)
    metrics = invoke("metrics", lambda: run_metrics_agent(events), trace, chaos=chaos)
    if metrics is None:
        incident.status = IncidentStatus.open
        incident.summary = "Investigation safely terminated after invocation limit"
        incident.timeline.append("Supervisor stopped investigation at the configured execution limit")
        incident.execution_trace = trace + [{"agent": "supervisor", "status": "terminated", "attempt": 1,
            "duration_ms": round((time.perf_counter() - started) * 1000, 2), "detail": "Invocation limit enforced"}]
        incident = update_incident(incident)
        return incident, None, SupervisorDecision(incident_id=incident.id, severity=incident.severity,
            summary=incident.summary, assigned_agents=["metrics"], next_action="stopped_at_execution_limit")
    logs = invoke("logs", lambda: run_logs_agent(events), trace)
    remediation = run_remediation_agent(events, [metrics, logs])
    if chaos == "unsafe_remediation":
        remediation.action = "disable_mock_security_controls"
        remediation.reason = "Injected unsafe high-risk recommendation for approval-gate demonstration."
        remediation.risk = RiskLevel.high
    risk = run_risk_agent(remediation.action if remediation.risk != "blocked" else "blocked")
    if remediation.risk == "high":
        risk.finding = "Remediation risk is high; human approval is mandatory"
        risk.evidence = ["risk:high", "approval:required"]
    similar = retrieve_similar_incidents(incident.service)
    context = invoke("context", lambda: run_context_agent(incident.service, [metrics, logs, risk], len(similar)), trace)
    incident.findings = [metrics, logs, context, risk]
    incident.context_pack = build_context_pack(incident.id, incident.service, events, incident.findings)
    incident.remediation = remediation
    incident.timeline.extend(
        [
            "Supervisor opened incident",
            "Metrics Agent analyzed latency",
            "Logs Agent grouped repeated failures",
            "Context Agent built compact evidence pack",
            "Risk Agent requested human approval",
        ]
    )
    incident.timeline.append("Supervisor decision: await human approval before mock execution")
    incident.summary = f"{incident.service} latency spike linked to {remediation.action}"
    approval = None
    if remediation.requires_approval:
        incident.status = IncidentStatus.awaiting_approval
        approval = create_approval(
            Approval(
                id=f"app_{uuid.uuid4().hex[:8]}",
                incident_id=incident.id,
                action=remediation.action,
                risk=remediation.risk,
                reason=remediation.reason,
                affected_service=incident.service,
                expected_impact=remediation.expected_impact,
            )
        )
    updated = update_incident(incident)
    updated.execution_trace = trace + [{"agent": "supervisor", "status": "completed", "attempt": 1,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
        "detail": "Degraded evidence accepted" if chaos == "agent_failure" else "Investigation completed"}]
    updated = update_incident(updated)
    return updated, approval, SupervisorDecision(
        incident_id=incident.id,
        severity=incident.severity,
        summary=incident.summary,
        assigned_agents=["metrics", "logs", "context", "risk", "remediation"],
        next_action="await_human_approval" if approval else "resolved",
    )
