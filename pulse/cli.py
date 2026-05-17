from __future__ import annotations

import sys

from pulse.api.main import _ensure_incident, _seed_events
from pulse.orchestration.supervisor import investigate_incident
from pulse.store import init_db, reset_db


def seed() -> None:
    reset_db()
    _seed_events()
    _ensure_incident("checkout-api")
    print("seeded")


def trigger_incident() -> None:
    init_db()
    _seed_events("checkout-api")
    incident = _ensure_incident("checkout-api")
    investigate_incident(incident.id)
    print(incident.id)


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "seed"
    {"seed": seed, "trigger-incident": trigger_incident}[action]()
