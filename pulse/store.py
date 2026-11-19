from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pulse.models import Approval, ApprovalState, Incident, MemoryEdge, MemoryNode, utcnow


DB_PATH = Path(os.getenv("PULSE_DB", Path(__file__).resolve().parents[1] / "pulse.db"))


def _json(value: object) -> str:
    return json.dumps(value)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            create table if not exists events (
              id text primary key,
              service text not null,
              kind text not null,
              summary text not null,
              payload text not null,
              created_at text not null
            );
            create table if not exists incidents (
              id text primary key,
              service text not null,
              severity text not null,
              status text not null,
              summary text not null,
              created_at text not null,
              updated_at text not null,
              timeline text not null,
              findings text not null,
              context_pack text,
              remediation text,
              postmortem text,
              execution_trace text not null default '[]',
              chaos text not null default '{}'
            );
            create table if not exists approvals (
              id text primary key,
              incident_id text not null,
              action text not null,
              risk text not null,
              reason text not null,
              affected_service text not null,
              expected_impact text not null,
              state text not null,
              created_at text not null,
              updated_at text not null
            );
            create table if not exists memory_nodes (
              id text primary key,
              type text not null,
              label text not null,
              payload text not null
            );
            create table if not exists memory_edges (
              id text primary key,
              source text not null,
              target text not null,
              kind text not null
            );
            """
        )
        columns = {row[1] for row in conn.execute("pragma table_info(incidents)")}
        if "execution_trace" not in columns:
            conn.execute("alter table incidents add column execution_trace text not null default '[]'")
        if "chaos" not in columns:
            conn.execute("alter table incidents add column chaos text not null default '{}'")


def reset_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            drop table if exists events;
            drop table if exists incidents;
            drop table if exists approvals;
            drop table if exists memory_nodes;
            drop table if exists memory_edges;
            """
        )
    init_db()


def add_event(service: str, kind: str, summary: str, payload: dict, created_at: str) -> str:
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            "insert into events values (?, ?, ?, ?, ?, ?)",
            (event_id, service, kind, summary, _json(payload), created_at),
        )
    return event_id


def list_events(service: str | None = None) -> list[dict]:
    with connect() as conn:
        if service:
            rows = conn.execute(
                "select * from events where service = ? order by created_at asc", (service,)
            ).fetchall()
        else:
            rows = conn.execute("select * from events order by created_at asc").fetchall()
    return [
        {
            **dict(row),
            "payload": json.loads(row["payload"]),
        }
        for row in rows
    ]


def create_incident(incident: Incident) -> Incident:
    with connect() as conn:
        conn.execute(
            """insert into incidents
            (id, service, severity, status, summary, created_at, updated_at, timeline,
             findings, context_pack, remediation, postmortem, execution_trace, chaos)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                incident.id,
                incident.service,
                incident.severity,
                incident.status.value,
                incident.summary,
                incident.created_at,
                incident.updated_at,
                _json(incident.timeline),
                _json([finding.model_dump() for finding in incident.findings]),
                _json(incident.context_pack.model_dump()) if incident.context_pack else None,
                _json(incident.remediation.model_dump()) if incident.remediation else None,
                _json(incident.postmortem) if incident.postmortem else None,
                _json(incident.execution_trace),
                _json(incident.chaos),
            ),
        )
    return incident


def update_incident(incident: Incident) -> Incident:
    incident.updated_at = utcnow()
    with connect() as conn:
        conn.execute(
            """
            update incidents
            set severity = ?, status = ?, summary = ?, updated_at = ?, timeline = ?,
                findings = ?, context_pack = ?, remediation = ?, postmortem = ?,
                execution_trace = ?, chaos = ?
            where id = ?
            """,
            (
                incident.severity,
                incident.status.value,
                incident.summary,
                incident.updated_at,
                _json(incident.timeline),
                _json([finding.model_dump() for finding in incident.findings]),
                _json(incident.context_pack.model_dump()) if incident.context_pack else None,
                _json(incident.remediation.model_dump()) if incident.remediation else None,
                _json(incident.postmortem) if incident.postmortem else None,
                _json(incident.execution_trace),
                _json(incident.chaos),
                incident.id,
            ),
        )
    return incident


def _load_incident(row: sqlite3.Row | None) -> Incident | None:
    if row is None:
        return None
    payload = dict(row)
    payload["timeline"] = json.loads(payload["timeline"])
    payload["findings"] = json.loads(payload["findings"])
    payload["context_pack"] = json.loads(payload["context_pack"]) if payload["context_pack"] else None
    payload["remediation"] = json.loads(payload["remediation"]) if payload["remediation"] else None
    payload["postmortem"] = json.loads(payload["postmortem"]) if payload["postmortem"] else None
    payload["execution_trace"] = json.loads(payload.get("execution_trace") or "[]")
    payload["chaos"] = json.loads(payload.get("chaos") or "{}")
    return Incident.model_validate(payload)


def get_incident(incident_id: str) -> Incident | None:
    with connect() as conn:
        row = conn.execute("select * from incidents where id = ?", (incident_id,)).fetchone()
    return _load_incident(row)


def list_incidents() -> list[Incident]:
    with connect() as conn:
        rows = conn.execute("select * from incidents order by created_at desc").fetchall()
    return [item for row in rows if (item := _load_incident(row))]


def find_open_incident(service: str) -> Incident | None:
    with connect() as conn:
        row = conn.execute(
            "select * from incidents where service = ? and status != 'resolved' order by created_at desc limit 1",
            (service,),
        ).fetchone()
    return _load_incident(row)


def create_approval(approval: Approval) -> Approval:
    with connect() as conn:
        conn.execute(
            "insert into approvals values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                approval.id,
                approval.incident_id,
                approval.action,
                approval.risk.value,
                approval.reason,
                approval.affected_service,
                approval.expected_impact,
                approval.state.value,
                approval.created_at,
                approval.updated_at,
            ),
        )
    return approval


def get_approval(approval_id: str) -> Approval | None:
    with connect() as conn:
        row = conn.execute("select * from approvals where id = ?", (approval_id,)).fetchone()
    return Approval.model_validate(dict(row)) if row else None


def list_approvals() -> list[Approval]:
    with connect() as conn:
        rows = conn.execute("select * from approvals order by created_at desc").fetchall()
    return [Approval.model_validate(dict(row)) for row in rows]


def update_approval_state(approval_id: str, state: ApprovalState) -> Approval | None:
    approval = get_approval(approval_id)
    if not approval:
        return None
    approval.state = state
    approval.updated_at = utcnow()
    with connect() as conn:
        conn.execute(
            "update approvals set state = ?, updated_at = ? where id = ?",
            (approval.state.value, approval.updated_at, approval.id),
        )
    return approval


def upsert_memory_node(node: MemoryNode) -> None:
    with connect() as conn:
        conn.execute(
            "insert or replace into memory_nodes values (?, ?, ?, ?)",
            (node.id, node.type, node.label, _json(node.payload)),
        )


def add_memory_edge(edge: MemoryEdge) -> None:
    with connect() as conn:
        conn.execute(
            "insert or replace into memory_edges values (?, ?, ?, ?)",
            (edge.id, edge.source, edge.target, edge.kind),
        )


def memory_graph() -> dict[str, list[dict]]:
    with connect() as conn:
        nodes = conn.execute("select * from memory_nodes").fetchall()
        edges = conn.execute("select * from memory_edges").fetchall()
    return {
        "nodes": [{**dict(row), "payload": json.loads(row["payload"])} for row in nodes],
        "edges": [dict(row) for row in edges],
    }


def similar_incidents(service: str) -> list[Incident]:
    return [incident for incident in list_incidents() if incident.service == service and incident.status == "resolved"][:3]
