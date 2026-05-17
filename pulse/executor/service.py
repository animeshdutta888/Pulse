from __future__ import annotations

import uuid

from pulse.approvals.service import require_approved
from pulse.models import ApprovalState, IncidentStatus, MemoryEdge, MemoryNode
from pulse.store import (
    add_memory_edge,
    get_incident,
    update_approval_state,
    update_incident,
    upsert_memory_node,
)


def generate_postmortem(incident_id: str) -> dict[str, object]:
    incident = get_incident(incident_id)
    if not incident:
        raise ValueError(f"Unknown incident {incident_id}")
    return {
        "summary": incident.summary,
        "timeline": incident.timeline,
        "root_cause": incident.findings[1].finding if incident.findings else "Unknown",
        "detection_signal": incident.findings[0].finding if incident.findings else "Unknown",
        "resolution": incident.remediation.action if incident.remediation else "No action",
        "what_went_well": ["Human approval prevented unsafe auto-execution."],
        "what_to_improve": ["Add richer traces in the next phase."],
        "follow_up_tasks": ["Tune latency alert thresholds."],
    }


def update_memory_graph(incident_id: str) -> None:
    incident = get_incident(incident_id)
    if not incident or not incident.remediation:
        return
    nodes = [
        MemoryNode(id=incident.id, type="Incident", label=incident.summary),
        MemoryNode(id=f"svc_{incident.service}", type="Service", label=incident.service),
        MemoryNode(id=f"rem_{incident.id}", type="Remediation", label=incident.remediation.action),
    ]
    for finding in incident.findings:
        nodes.append(
            MemoryNode(
                id=f"finding_{incident.id}_{finding.agent}",
                type="Agent Finding",
                label=finding.finding,
            )
        )
    for node in nodes:
        upsert_memory_node(node)
    add_memory_edge(
        MemoryEdge(id=f"edge_{uuid.uuid4().hex[:8]}", source=incident.id, target=f"svc_{incident.service}", kind="affected_service")
    )
    add_memory_edge(
        MemoryEdge(id=f"edge_{uuid.uuid4().hex[:8]}", source=incident.id, target=f"rem_{incident.id}", kind="fixed_by")
    )


def run_executor(approval_id: str) -> dict[str, str]:
    approval = require_approved(approval_id)
    incident = get_incident(approval.incident_id)
    if not incident:
        raise ValueError(f"Unknown incident {approval.incident_id}")
    incident.timeline.append(f"Executor ran {approval.action}")
    incident.status = IncidentStatus.resolved
    incident.postmortem = generate_postmortem(incident.id)
    update_incident(incident)
    update_approval_state(approval.id, ApprovalState.executed)
    update_memory_graph(incident.id)
    return {"status": "executed", "action": approval.action, "incident_id": incident.id}
