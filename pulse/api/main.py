from __future__ import annotations

import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from pulse.approvals.service import approve, reject
from pulse.executor.service import run_executor
from pulse.models import EventIn, Incident, IncidentStatus
from pulse.observability.service import dashboard_snapshot
from pulse.orchestration.supervisor import investigate_incident
from pulse.store import (
    add_event,
    create_incident,
    find_open_incident,
    get_incident,
    init_db,
    list_approvals,
    list_incidents,
    memory_graph,
    reset_db,
)

app = FastAPI(title="Pulse")


@app.on_event("startup")
def startup() -> None:
    init_db()


def _seed_events(service: str = "checkout-api") -> None:
    demo_events = [
        EventIn(service=service, kind="metric", summary="Baseline latency", payload={"latency_ms": 230}),
        EventIn(service=service, kind="deploy", summary="Recent deploy shipped", payload={"version": "2026.05.17"}),
        EventIn(service=service, kind="metric", summary="Latency spike", payload={"latency_ms": 1900}),
        EventIn(service=service, kind="log", summary="upstream timeout", payload={"count": 3}),
        EventIn(service=service, kind="log", summary="upstream timeout", payload={"count": 5}),
    ]
    for event in demo_events:
        add_event(**event.model_dump())


def _ensure_incident(service: str) -> Incident:
    existing = find_open_incident(service)
    if existing:
        return existing
    incident = Incident(
        id=f"inc_{uuid.uuid4().hex[:8]}",
        service=service,
        severity="medium",
        status=IncidentStatus.open,
        summary=f"High latency detected for {service}",
        timeline=["Telemetry ingestion detected abnormal latency"],
    )
    return create_incident(incident)


def _html(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><title>{title}</title>"
        "<meta name='viewport' content='width=device-width, initial-scale=1' /></head>"
        f"<body>{body}</body></html>"
    )


def _dashboard_shell() -> str:
    return """
    <style>
      :root {
        --bg: #09111f;
        --panel: rgba(11, 23, 40, 0.82);
        --panel-strong: #0f1c31;
        --line: rgba(148, 163, 184, 0.16);
        --text: #edf4ff;
        --muted: #92a7c5;
        --good: #5eead4;
        --warn: #fbbf24;
        --bad: #fb7185;
        --accent: #7dd3fc;
        --accent-2: #93c5fd;
        --shadow: 0 24px 80px rgba(2, 6, 23, 0.42);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
        color: var(--text);
        background:
          radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 26%),
          radial-gradient(circle at top right, rgba(251, 191, 36, 0.12), transparent 22%),
          linear-gradient(180deg, #07101d 0%, #0c1628 45%, #09111f 100%);
      }
      .shell { max-width: 1280px; margin: 0 auto; padding: 28px 20px 56px; }
      .hero {
        display: grid; gap: 16px; margin-bottom: 22px; padding: 24px;
        background: linear-gradient(135deg, rgba(10, 20, 38, 0.92), rgba(15, 28, 49, 0.88));
        border: 1px solid var(--line); border-radius: 28px; box-shadow: var(--shadow);
      }
      .eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: 0.18em; font-size: 12px; }
      h1 { margin: 0; font-size: clamp(34px, 5vw, 52px); line-height: 0.96; }
      .hero p { margin: 0; color: var(--muted); max-width: 760px; font-size: 16px; }
      .hero-actions, .approval-actions { display: flex; flex-wrap: wrap; gap: 12px; }
      button {
        border: 0; cursor: pointer; color: #08111d; font-weight: 700; padding: 12px 16px;
        border-radius: 14px; background: linear-gradient(135deg, var(--accent), var(--accent-2));
      }
      button.secondary { background: rgba(148, 163, 184, 0.12); color: var(--text); border: 1px solid var(--line); }
      button.warn { background: linear-gradient(135deg, #f59e0b, #f97316); color: #101010; }
      button.bad { background: linear-gradient(135deg, #fb7185, #ef4444); color: white; }
      button:disabled { opacity: 0.5; cursor: wait; }
      .status-line { color: var(--muted); min-height: 20px; }
      .metrics {
        display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        margin: 18px 0 26px;
      }
      .metric, .panel {
        background: var(--panel); border: 1px solid var(--line); border-radius: 22px; box-shadow: var(--shadow);
        backdrop-filter: blur(10px);
      }
      .metric { padding: 18px; }
      .metric-label { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; }
      .metric-value { font-size: 30px; margin-top: 10px; font-weight: 700; }
      .grid { display: grid; gap: 16px; grid-template-columns: 1.25fr 0.75fr; }
      .stack { display: grid; gap: 16px; }
      .panel { padding: 20px; }
      .panel h2, .panel h3 { margin: 0 0 14px; font-size: 18px; }
      .incident-header {
        display: flex; justify-content: space-between; gap: 16px; align-items: start; margin-bottom: 14px;
      }
      .incident-title { margin: 0 0 8px; font-size: 28px; }
      .meta, .small { color: var(--muted); font-size: 14px; }
      .badge {
        display: inline-flex; align-items: center; gap: 8px; border-radius: 999px; padding: 8px 12px;
        background: rgba(125, 211, 252, 0.12); color: var(--accent); border: 1px solid rgba(125, 211, 252, 0.22);
        font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em;
      }
      .badge.warn { color: var(--warn); background: rgba(251, 191, 36, 0.12); border-color: rgba(251, 191, 36, 0.22); }
      .badge.good { color: var(--good); background: rgba(94, 234, 212, 0.12); border-color: rgba(94, 234, 212, 0.22); }
      .timeline, .finding-list, .postmortem-list, .memory-list { display: grid; gap: 12px; }
      .timeline-item, .finding, .memory-item {
        padding: 14px; border-radius: 16px; border: 1px solid var(--line); background: rgba(148, 163, 184, 0.05);
      }
      .timeline-item strong, .finding strong { display: block; margin-bottom: 6px; }
      .finding-top, .approval-top { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
      .finding-evidence { margin-top: 8px; color: var(--muted); font-size: 13px; }
      .approval-card {
        padding: 18px; border-radius: 18px; border: 1px solid rgba(251, 191, 36, 0.24);
        background: linear-gradient(180deg, rgba(251, 191, 36, 0.12), rgba(15, 23, 42, 0.5));
      }
      .approval-empty, .empty {
        padding: 16px; border: 1px dashed var(--line); border-radius: 16px; color: var(--muted);
      }
      .kv { display: grid; gap: 8px; margin: 14px 0; }
      .kv div { display: flex; justify-content: space-between; gap: 12px; color: var(--muted); }
      .kv span:last-child { color: var(--text); text-align: right; }
      .postmortem-list div { padding: 12px 0; border-top: 1px solid var(--line); }
      .postmortem-list div:first-child { border-top: 0; padding-top: 0; }
      .mono { font-family: "IBM Plex Mono", "SFMono-Regular", monospace; }
      @media (max-width: 980px) { .grid { grid-template-columns: 1fr; } }
    </style>
    <div class="shell">
      <section class="hero">
        <div class="eyebrow">Pulse Phase 1 Demo</div>
        <h1>AI operations cockpit for agentic incident response.</h1>
        <p>Trigger a latency incident, watch specialist agents investigate, require approval before remediation, and resolve into operational memory.</p>
        <div class="hero-actions">
          <button id="seed-btn">Seed Demo</button>
          <button id="trigger-btn" class="warn">Trigger Incident</button>
          <button id="refresh-btn" class="secondary">Refresh</button>
        </div>
        <div class="status-line" id="status-line">Waiting for demo data.</div>
      </section>
      <section class="metrics" id="metrics"></section>
      <section class="grid">
        <div class="stack">
          <article class="panel">
            <div class="incident-header">
              <div>
                <div class="small">Active Incident</div>
                <h2 class="incident-title" id="incident-title">No incident loaded</h2>
                <div class="meta mono" id="incident-meta">Seed the demo to begin.</div>
              </div>
              <div id="incident-badges"></div>
            </div>
            <div class="meta" id="incident-summary"></div>
          </article>
          <article class="panel">
            <h3>Agent Timeline</h3>
            <div class="timeline" id="timeline"></div>
          </article>
          <article class="panel">
            <h3>Agent Findings</h3>
            <div class="finding-list" id="findings"></div>
          </article>
          <article class="panel">
            <h3>Postmortem Preview</h3>
            <div class="postmortem-list" id="postmortem"></div>
          </article>
        </div>
        <div class="stack">
          <article class="panel">
            <h3>Approval Panel</h3>
            <div id="approval-slot"></div>
          </article>
          <article class="panel">
            <h3>Remediation Status</h3>
            <div id="remediation-slot"></div>
          </article>
          <article class="panel">
            <h3>Memory Matches</h3>
            <div class="memory-list" id="memory-slot"></div>
          </article>
        </div>
      </section>
    </div>
    <script>
      const state = { incident: null, approval: null, snapshot: null, graph: null };
      const $ = (id) => document.getElementById(id);
      const fmt = (value) => value ? String(value).replaceAll("_", " ") : "n/a";
      const badge = (label, tone = "") => `<span class="badge ${tone}">${label}</span>`;
      const setStatus = (text) => { $("status-line").textContent = text; };

      function renderMetrics(snapshot) {
        const cards = [
          ["Active Incidents", snapshot.active_incidents],
          ["Service Health", snapshot.service_health],
          ["P95 Latency", `${snapshot.p95_latency}ms`],
          ["Error Events", snapshot.error_rate],
          ["Pending Approvals", snapshot.pending_approvals],
          ["Token Usage", snapshot.token_usage],
        ];
        $("metrics").innerHTML = cards.map(([label, value]) => `
          <div class="metric">
            <div class="metric-label">${label}</div>
            <div class="metric-value">${value}</div>
          </div>
        `).join("");
      }

      function renderIncident(incident) {
        $("incident-title").textContent = incident ? incident.service : "No incident loaded";
        $("incident-meta").textContent = incident ? `${incident.id} • opened ${incident.created_at}` : "Seed the demo to begin.";
        $("incident-summary").textContent = incident ? incident.summary : "";
        $("incident-badges").innerHTML = incident ? [
          badge(fmt(incident.status), incident.status === "resolved" ? "good" : "warn"),
          badge(`Severity ${incident.severity}`),
        ].join(" ") : "";
      }

      function renderTimeline(incident) {
        $("timeline").innerHTML = incident && incident.timeline.length ? incident.timeline.map((item, index) => `
          <div class="timeline-item">
            <strong>Step ${index + 1}</strong>
            <div>${item}</div>
          </div>
        `).join("") : `<div class="empty">No agent activity yet.</div>`;
      }

      function renderFindings(incident) {
        $("findings").innerHTML = incident && incident.findings.length ? incident.findings.map((finding) => `
          <div class="finding">
            <div class="finding-top">
              <strong>${finding.agent}</strong>
              ${badge(`${Math.round(finding.confidence * 100)}% confidence`)}
            </div>
            <div>${finding.finding}</div>
            <div class="finding-evidence">${finding.evidence.join(" • ")}</div>
          </div>
        `).join("") : `<div class="empty">Investigation results will appear here.</div>`;
      }

      function renderApproval(approval) {
        if (!approval) {
          $("approval-slot").innerHTML = `<div class="approval-empty">No pending approval. Trigger an incident to create a suggested fix.</div>`;
          return;
        }
        const pending = approval.state === "pending";
        $("approval-slot").innerHTML = `
          <div class="approval-card">
            <div class="approval-top">
              <strong>${fmt(approval.action)}</strong>
              ${badge(fmt(approval.state), approval.state === "executed" ? "good" : "warn")}
            </div>
            <div class="kv">
              <div><span>Risk</span><span>${approval.risk}</span></div>
              <div><span>Service</span><span>${approval.affected_service}</span></div>
              <div><span>Impact</span><span>${approval.expected_impact}</span></div>
            </div>
            <div class="small">${approval.reason}</div>
            <div class="approval-actions" style="margin-top:14px">
              <button id="approve-btn" ${pending ? "" : "disabled"}>Approve</button>
              <button id="reject-btn" class="secondary" ${pending ? "" : "disabled"}>Reject</button>
              <button id="execute-btn" class="bad" ${(approval.state === "approved") ? "" : "disabled"}>Execute</button>
            </div>
          </div>
        `;
        if (pending) {
          $("approve-btn").onclick = () => act(`/approvals/${approval.id}/approve`, "Approval granted.");
          $("reject-btn").onclick = () => act(`/approvals/${approval.id}/reject`, "Approval rejected.");
        }
        if (approval.state === "approved") {
          $("execute-btn").onclick = () => act(`/executor/run/${approval.id}`, "Remediation executed.");
        }
      }

      function renderRemediation(incident, approval) {
        if (!incident || !incident.remediation) {
          $("remediation-slot").innerHTML = `<div class="empty">No remediation recommendation yet.</div>`;
          return;
        }
        const stateLabel = approval ? approval.state : (incident.status === "resolved" ? "executed" : "draft");
        $("remediation-slot").innerHTML = `
          <div class="timeline-item">
            <strong>${fmt(incident.remediation.action)}</strong>
            <div class="small">${incident.remediation.reason}</div>
            <div class="kv">
              <div><span>Risk</span><span>${incident.remediation.risk}</span></div>
              <div><span>Approval</span><span>${stateLabel}</span></div>
              <div><span>Expected impact</span><span>${incident.remediation.expected_impact}</span></div>
            </div>
          </div>
        `;
      }

      function renderPostmortem(incident) {
        const postmortem = incident && incident.postmortem;
        if (!postmortem) {
          $("postmortem").innerHTML = `<div class="empty">Postmortem appears after execution.</div>`;
          return;
        }
        const entries = [
          ["Summary", postmortem.summary],
          ["Root Cause", postmortem.root_cause],
          ["Detection", postmortem.detection_signal],
          ["Resolution", postmortem.resolution],
        ];
        $("postmortem").innerHTML = entries.map(([label, value]) => `
          <div><strong>${label}</strong><div class="small">${value}</div></div>
        `).join("");
      }

      function renderMemory(graph, incident) {
        const relevant = graph && incident ? graph.nodes.filter((node) =>
          node.id === incident.id || node.id === `svc_${incident.service}` || node.id === `rem_${incident.id}` || node.id.startsWith(`finding_${incident.id}_`)
        ) : [];
        $("memory-slot").innerHTML = relevant.length ? relevant.map((node) => `
          <div class="memory-item">
            <strong>${node.type}</strong>
            <div class="small">${node.label}</div>
          </div>
        `).join("") : `<div class="empty">Resolved incidents write back here as reusable operational memory.</div>`;
      }

      async function act(url, successText) {
        setStatus("Applying action...");
        await fetch(url, { method: "POST" });
        await refresh();
        setStatus(successText);
      }

      async function seed() {
        setStatus("Seeding demo data...");
        await fetch("/demo/seed");
        await refresh();
        setStatus("Demo seeded. Trigger the incident when ready.");
      }

      async function trigger() {
        setStatus("Triggering incident and launching specialist agents...");
        await fetch("/demo/trigger-incident", { method: "POST" });
        await refresh();
        setStatus("Incident is live. Approval is now required before remediation.");
      }

      async function refresh() {
        const response = await fetch("/dashboard/data");
        const data = await response.json();
        state.snapshot = data.snapshot;
        state.incident = data.incident;
        state.approval = data.approval;
        state.graph = data.graph;
        renderMetrics(data.snapshot);
        renderIncident(data.incident);
        renderTimeline(data.incident);
        renderFindings(data.incident);
        renderApproval(data.approval);
        renderRemediation(data.incident, data.approval);
        renderPostmortem(data.incident);
        renderMemory(data.graph, data.incident);
      }

      $("seed-btn").onclick = seed;
      $("trigger-btn").onclick = trigger;
      $("refresh-btn").onclick = refresh;
      refresh().catch(() => setStatus("Dashboard could not load data yet."));
    </script>
    """


@app.get("/", response_class=HTMLResponse)
def landing() -> HTMLResponse:
    return _html(
        "Pulse",
        """
        <main style="font-family:'IBM Plex Sans','Segoe UI',sans-serif;max-width:880px;margin:60px auto;padding:0 20px;color:#e8eef8">
          <div style="padding:32px;border-radius:28px;background:linear-gradient(135deg,#0d1a2f,#111f37);border:1px solid rgba(148,163,184,.18)">
            <div style="color:#7dd3fc;text-transform:uppercase;letter-spacing:.18em;font-size:12px">Pulse</div>
            <h1 style="font-size:48px;line-height:1;margin:8px 0 14px">AI operations cockpit for agentic incident response.</h1>
            <p style="color:#9fb0c9;font-size:18px;max-width:700px">Demo a full incident workflow with seeded telemetry, specialist investigation, human approval, safe execution, and memory writeback.</p>
            <div style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap">
              <a href="/dashboard" style="padding:14px 18px;border-radius:14px;background:#7dd3fc;color:#07111d;text-decoration:none;font-weight:700">Open Dashboard</a>
              <a href="/memory" style="padding:14px 18px;border-radius:14px;border:1px solid rgba(148,163,184,.2);color:#e8eef8;text-decoration:none">Memory View</a>
            </div>
          </div>
        </main>
        <style>body{margin:0;background:linear-gradient(180deg,#07101d,#0b1424)}</style>
        """,
    )


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page() -> HTMLResponse:
    return _html("Dashboard", _dashboard_shell())


@app.get("/ui/approvals", response_class=HTMLResponse)
def approvals_page() -> HTMLResponse:
    return _html("Approvals", f"<pre>{json.dumps([item.model_dump() for item in list_approvals()], indent=2)}</pre>")


@app.get("/memory", response_class=HTMLResponse)
def memory_page() -> HTMLResponse:
    return _html("Memory Graph", f"<pre>{json.dumps(memory_graph(), indent=2)}</pre>")


@app.get("/ui/incidents/{incident_id}", response_class=HTMLResponse)
def incident_page(incident_id: str) -> HTMLResponse:
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return _html(f"Incident {incident_id}", f"<pre>{json.dumps(incident.model_dump(), indent=2)}</pre>")


@app.get("/dashboard/data")
def dashboard_data() -> dict:
    incidents = list_incidents()
    incident = incidents[0].model_dump() if incidents else None
    incident_id = incident["id"] if incident else None
    approval = next(
        (item.model_dump() for item in list_approvals() if not incident_id or item.incident_id == incident_id),
        None,
    )
    return {
        "snapshot": dashboard_snapshot(),
        "incident": incident,
        "approval": approval,
        "graph": memory_graph(),
    }


@app.post("/events/ingest")
def ingest_event(event: EventIn) -> dict[str, str]:
    event_id = add_event(**event.model_dump())
    incident_id = ""
    if event.kind == "metric" and event.payload.get("latency_ms", 0) >= 1000:
        incident_id = _ensure_incident(event.service).id
    return {"event_id": event_id, "incident_id": incident_id}


@app.get("/incidents")
def incidents() -> list[dict]:
    return [incident.model_dump() for incident in list_incidents()]


@app.get("/incidents/{incident_id}")
def incident_detail(incident_id: str) -> dict:
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident.model_dump()


@app.post("/incidents/{incident_id}/investigate")
def investigate(incident_id: str) -> dict:
    try:
        incident, approval, decision = investigate_incident(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "incident": incident.model_dump(),
        "approval": approval.model_dump() if approval else None,
        "decision": decision.model_dump(),
    }


@app.get("/approvals")
def approvals() -> list[dict]:
    return [approval.model_dump() for approval in list_approvals()]


@app.post("/approvals/{approval_id}/approve")
def approve_route(approval_id: str) -> dict:
    try:
        return approve(approval_id).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/approvals/{approval_id}/reject")
def reject_route(approval_id: str) -> dict:
    try:
        return reject(approval_id).model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/executor/run/{approval_id}")
def executor_run(approval_id: str) -> dict:
    try:
        return run_executor(approval_id)
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/memory/graph")
def graph() -> dict[str, list[dict]]:
    return memory_graph()


@app.get("/demo/seed")
def seed_demo() -> dict[str, str]:
    reset_db()
    _seed_events()
    incident = _ensure_incident("checkout-api")
    return {"status": "seeded", "incident_id": incident.id}


@app.post("/demo/trigger-incident")
def trigger_incident() -> dict:
    _seed_events("checkout-api")
    incident = _ensure_incident("checkout-api")
    investigated, approval, decision = investigate_incident(incident.id)
    return {
        "incident": investigated.model_dump(),
        "approval": approval.model_dump() if approval else None,
        "decision": decision.model_dump(),
    }
