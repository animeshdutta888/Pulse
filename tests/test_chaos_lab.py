def test_agent_failure_continues_with_degraded_evidence(client):
    body = client.post("/demo/run/agent_failure").json()
    incident = body["incident"]
    assert incident["chaos"]["enabled"] is True
    assert incident["status"] == "awaiting_approval"
    assert any(row["status"] == "failed" for row in incident["execution_trace"])
    assert any("degraded evidence" in finding["finding"] for finding in incident["findings"])


def test_infinite_loop_is_bounded_and_stopped(client):
    body = client.post("/demo/run/infinite_loop").json()
    incident = body["incident"]
    assert incident["status"] == "open"
    assert body["decision"]["next_action"] == "stopped_at_execution_limit"
    assert any(row["status"] == "terminated" for row in incident["execution_trace"])


def test_unsafe_remediation_remains_approval_gated(client):
    body = client.post("/demo/run/unsafe_remediation").json()
    incident = body["incident"]
    approval = body["approval"]
    assert incident["status"] == "awaiting_approval"
    assert incident["remediation"]["risk"] == "high"
    assert approval["state"] == "pending"
    assert approval["action"] == "disable_mock_security_controls"


def test_normal_mode_has_no_chaos_and_comparison_data(client):
    response = client.post("/demo/run/baseline")
    assert response.status_code == 200
    incident = response.json()["incident"]
    assert incident["chaos"]["enabled"] is False
    data = client.get("/dashboard/data").json()
    assert data["incidents"]
