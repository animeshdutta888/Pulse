def test_supervisor_assigns_agents_and_waits_for_approval(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    response = client.post(f"/incidents/{incident_id}/investigate")
    body = response.json()
    assert response.status_code == 200
    assert body["decision"]["assigned_agents"] == ["metrics", "logs", "context", "risk", "remediation"]
    assert body["decision"]["next_action"] == "await_human_approval"
