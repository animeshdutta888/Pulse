# Pulse

Pulse is a Phase 1 MVP for an AI operations cockpit. It demonstrates an end-to-end incident workflow: telemetry ingestion, incident creation, specialist investigation, human approval before remediation, mock execution, postmortem generation, and memory graph updates.

The current version is intentionally lightweight:

- FastAPI backend
- SQLite storage
- Vanilla JS dashboard
- Deterministic specialist agents for demo flow
- CLI helpers for seeding and triggering incidents

## Current Demo Scope

Pulse currently proves these pieces:

- Event ingestion opens an incident on high latency
- Supervisor orchestration calls specialist agents
- Metrics, logs, context, risk, and remediation findings are merged
- Remediation is blocked until approval
- Executor resolves the incident only after approval
- Postmortem data is generated after execution
- Memory graph is updated after resolution

This is a workflow MVP, not a full autonomous AI system yet.

## AI Agent Chaos Lab

The dashboard includes an opt-in Chaos Mode for the talk “Break the Agent: Chaos Engineering for AI Systems”. Faults are deterministic simulations; they never call real infrastructure and are disabled in normal investigations.

Run the app with `make dev`, open `/dashboard`, and use the guided buttons:

1. `Normal baseline` records a healthy investigation for comparison.
2. `Metrics agent timeout` fails the metrics specialist and shows the supervisor continuing with degraded evidence.
3. `Repeated invocation limit` simulates an infinite loop and stops safely after the execution limit.
4. `Unsafe remediation gate` injects a high-risk recommendation and leaves it pending until the existing human approval flow is used.

The dashboard records agent status, failures, retries, invocation counts, supervisor decisions, durations, and a timeline. `Reset demo` clears the local SQLite demo state so the sequence can be repeated.

The HTTP equivalents are `POST /demo/run/baseline`, `POST /demo/run/agent_failure`, `POST /demo/run/infinite_loop`, `POST /demo/run/unsafe_remediation`, and `POST /demo/reset`.

## Architecture

```text
Dashboard UI (Vanilla JS)
        |
        v
FastAPI App
  |- Landing Page
  |- Dashboard Page
  |- API Routes
        |
        v
Event Ingestion
        |
        v
SQLite Store
  |- Events
  |- Incidents
  |- Approvals
  |- Memory Graph
        |
        v
Supervisor
  |- Metrics Agent
  |- Logs Agent
  |- Context Agent
  |- Risk Agent
  |- Remediation Agent
        |
        v
Approval Gate
        |
        v
Executor
        |
        v
Postmortem + Memory Update
```

## Project Layout

```text
Pulse/
  pulse/
    agents/
    api/
    approvals/
    context/
    executor/
    observability/
    orchestration/
    models.py
    store.py
    cli.py
  tests/
  Makefile
  pyproject.toml
```

## Run The Dashboard

From the project root:

```bash
python3 -m pip install -e '.[test]'
make dev
```

Then open:

- `http://127.0.0.1:8000/`
- `http://127.0.0.1:8000/dashboard`

Recommended demo flow:

1. Click `Seed Demo`
2. Click `Trigger Incident`
3. Review the incident card, timeline, findings, and approval panel
4. Click `Approve`
5. Click `Execute`
6. Show the postmortem preview and memory updates

## Run The CLI

Seed the demo data:

```bash
make seed
```

Trigger an incident from CLI:

```bash
make trigger-incident
```

Run tests:

```bash
make test
```

You can also use the module entrypoints directly:

```bash
python3 -m pulse.cli seed
python3 -m pulse.cli trigger-incident
```

## Key Routes

UI routes:

- `GET /`
- `GET /dashboard`
- `GET /memory`

Core API routes:

- `POST /events/ingest`
- `GET /incidents`
- `GET /incidents/{id}`
- `POST /incidents/{id}/investigate`
- `GET /approvals`
- `POST /approvals/{id}/approve`
- `POST /approvals/{id}/reject`
- `POST /executor/run/{approval_id}`
- `GET /memory/graph`
- `GET /demo/seed`
- `POST /demo/trigger-incident`

## How It Works Today

The current specialist agents are deterministic Python functions, not live LLM-backed agents.

- Metrics Agent compares latency values
- Logs Agent groups repeated log summaries
- Context Agent builds a compact context pack
- Risk Agent marks remediation as approval-gated
- Remediation Agent returns a safe mock action

This keeps the MVP fast, testable, and easy to demo while preserving the intended architecture.

## Future Scope

Short-term upgrades:

- Replace deterministic log/context analysis with Ollama or model-backed reasoning
- Add multiple incident scenarios instead of a single seeded path
- Improve memory graph usefulness with similarity search
- Move startup hooks to FastAPI lifespan
- Add richer dashboard visualizations for metrics and approvals

Longer-term scope:

- Real observability ingestion
- Background workers
- Multi-service incident correlation
- Safer remediation playbooks
- Deployable hosted frontend/backend split
