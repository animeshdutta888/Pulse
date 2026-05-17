from __future__ import annotations

import uuid

from pulse.agents.specialists import (
    run_context_agent,
    run_logs_agent,
    run_metrics_agent,
    run_remediation_agent,
    run_risk_agent,
)
from pulse.context.engine import build_context_pack, retrieve_similar_incidents
from pulse.models import Approval, Incident, IncidentStatus, SupervisorDecision
from pulse.store import create_approval, get_incident, list_events, update_incident


def investigate_incident(incident_id: str) -> tuple[Incident, Approval | None, SupervisorDecision]:
    incident = get_incident(incident_id)
    if not incident:
        raise ValueError(f"Unknown incident {incident_id}")

    incident.status = IncidentStatus.investigating
    events = list_events(incident.service)
    metrics = run_metrics_agent(events)
    logs = run_logs_agent(events)
    remediation = run_remediation_agent(events, [metrics, logs])
    risk = run_risk_agent(remediation.action if remediation.risk != "blocked" else "blocked")
    similar = retrieve_similar_incidents(incident.service)
    context = run_context_agent(incident.service, [metrics, logs, risk], len(similar))
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
    return updated, approval, SupervisorDecision(
        incident_id=incident.id,
        severity=incident.severity,
        summary=incident.summary,
        assigned_agents=["metrics", "logs", "context", "risk", "remediation"],
        next_action="await_human_approval" if approval else "resolved",
    )
