from __future__ import annotations

from collections import Counter

from pulse.models import AgentFinding, RemediationRecommendation, RiskLevel


def run_metrics_agent(events: list[dict]) -> AgentFinding:
    latencies = [event["payload"].get("latency_ms", 0) for event in events if event["kind"] == "metric"]
    current = max(latencies or [0])
    baseline = min(latencies or [0])
    finding = f"p95 latency increased from {baseline}ms to {current}ms"
    return AgentFinding(
        agent="metrics",
        finding=finding,
        confidence=0.87 if current > 1000 else 0.52,
        evidence=["metric:p95_latency", f"latency:{current}"],
    )


def run_logs_agent(events: list[dict]) -> AgentFinding:
    messages = [event["summary"] for event in events if event["kind"] == "log"]
    common, count = Counter(messages).most_common(1)[0] if messages else ("no repeated errors", 0)
    return AgentFinding(
        agent="logs",
        finding=f"{common} repeated {count} times",
        confidence=0.81 if count else 0.35,
        evidence=[f"log:{common}"],
    )


def run_context_agent(service: str, findings: list[AgentFinding], similar_count: int) -> AgentFinding:
    return AgentFinding(
        agent="context",
        finding=f"Selected {len(findings)} evidence items and {similar_count} similar incidents for {service}",
        confidence=0.74,
        evidence=[finding.agent for finding in findings],
    )


def run_risk_agent(action: str) -> AgentFinding:
    risk = "medium" if action != "blocked" else "blocked"
    return AgentFinding(
        agent="risk",
        finding=f"Remediation risk is {risk}",
        confidence=0.79,
        evidence=[f"risk:{risk}"],
    )


def run_remediation_agent(events: list[dict], findings: list[AgentFinding]) -> RemediationRecommendation:
    joined = " ".join(finding.finding for finding in findings).lower()
    if "deploy" in joined or any(event["kind"] == "deploy" for event in events):
        return RemediationRecommendation(
            action="rollback_mock_deployment",
            reason="Recent deploy appears correlated with the latency spike.",
            risk=RiskLevel.medium,
            expected_impact="Should restore the previous healthy release path.",
        )
    if "timeout" in joined or "latency" in joined:
        return RemediationRecommendation(
            action="increase_mock_timeout",
            reason="Service is slow but still responding, so widening the timeout is the safest demo action.",
            risk=RiskLevel.medium,
            expected_impact="Reduces user-facing failures while investigation completes.",
        )
    return RemediationRecommendation(
        action="restart_mock_service",
        reason="Repeated errors suggest the mock service is wedged.",
        risk=RiskLevel.low,
        expected_impact="May clear transient failures with limited blast radius.",
    )
