from __future__ import annotations

from pulse.store import list_events, list_incidents, list_approvals


def dashboard_snapshot() -> dict[str, object]:
    events = list_events()
    incidents = list_incidents()
    approvals = list_approvals()
    latencies = [event["payload"].get("latency_ms", 0) for event in events if event["kind"] == "metric"]
    errors = [event for event in events if event["kind"] == "log"]
    return {
        "active_incidents": len([item for item in incidents if item.status != "resolved"]),
        "service_health": "degraded" if incidents else "healthy",
        "p95_latency": max(latencies or [0]),
        "error_rate": len(errors),
        "pending_approvals": len([item for item in approvals if item.state == "pending"]),
        "memory_matches": sum(1 for incident in incidents if incident.context_pack and incident.context_pack.included),
        "token_usage": sum(incident.context_pack.tokens_estimated for incident in incidents if incident.context_pack),
        "agent_activity_timeline": [entry for incident in incidents for entry in incident.timeline][-6:],
    }
