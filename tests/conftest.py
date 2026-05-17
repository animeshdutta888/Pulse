from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PULSE_DB", str(tmp_path / "pulse-test.db"))
    from pulse import store

    store.DB_PATH = Path(os.environ["PULSE_DB"])
    store.reset_db()

    from pulse.api.main import app

    with TestClient(app) as test_client:
        yield test_client
