from __future__ import annotations

import uuid

from pulse.models import AgentFinding, ContextPack
from pulse.store import similar_incidents


def estimate_tokens(text: str) -> int:
    return max(1, len(text.split()) * 2)


def rank_evidence(events: list[dict]) -> list[str]:
    important = []
    for event in events:
        if event["kind"] in {"metric", "log", "deploy"}:
            important.append(event["summary"])
    return important[:4]


def compress_logs(logs: list[str]) -> str:
    return " | ".join(logs[:3])


def retrieve_similar_incidents(service: str) -> list[str]:
    return [incident.id for incident in similar_incidents(service)]


def build_context_pack(incident_id: str, service: str, events: list[dict], findings: list[AgentFinding]) -> ContextPack:
    evidence = rank_evidence(events)
    similar = retrieve_similar_incidents(service)
    compressed = compress_logs([event["summary"] for event in events if event["kind"] == "log"])
    included = evidence + ([compressed] if compressed else []) + similar
    return ContextPack(
        context_pack_id=f"ctx_{incident_id}_{uuid.uuid4().hex[:4]}",
        tokens_estimated=estimate_tokens(" ".join(included)),
        included=included[:6],
        excluded=["unrelated auth logs"] if not any("auth" in item.lower() for item in included) else [],
    )
