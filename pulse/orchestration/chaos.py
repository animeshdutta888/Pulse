"""Opt-in, deterministic fault injection kept outside specialist agent logic."""
from __future__ import annotations

import time

from pulse.models import AgentFinding

SCENARIOS = {
    "agent_failure": "Metrics Agent failure: continue with degraded evidence",
    "infinite_loop": "Repeated invocation: stop at the execution limit",
    "unsafe_remediation": "High-risk recommendation: hold for human approval",
}


def invoke(agent: str, operation, trace: list[dict], *, chaos: str | None = None, limit: int = 2):
    """Invoke a specialist with bounded retries and visible, simulated faults."""
    count = 3 if chaos == "infinite_loop" and agent == "metrics" else 1
    for attempt in range(1, min(count, limit) + 1):
        started = time.perf_counter()
        if chaos == "agent_failure" and agent == "metrics":
            trace.append({"agent": agent, "status": "failed", "attempt": attempt,
                          "duration_ms": 0, "detail": "Injected timeout (simulated); no infrastructure call"})
            return AgentFinding(agent="metrics", finding="Metrics unavailable after simulated timeout; continuing with degraded evidence",
                                confidence=0.0, evidence=["metrics:unavailable", "chaos:agent_failure"])
        if chaos == "infinite_loop" and agent == "metrics":
            trace.append({"agent": agent, "status": "retrying", "attempt": attempt,
                          "duration_ms": 0, "detail": "Injected repeated invocation"})
            continue
        result = operation()
        trace.append({"agent": agent, "status": "completed", "attempt": attempt,
                      "duration_ms": round((time.perf_counter() - started) * 1000, 2), "detail": ""})
        return result
    trace.append({"agent": agent, "status": "terminated", "attempt": limit,
                  "duration_ms": 0, "detail": f"Execution limit ({limit}) reached; investigation stopped safely"})
    return None
