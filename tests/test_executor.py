def test_executor_resolves_incident_and_generates_postmortem(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    approval = client.post(f"/incidents/{incident_id}/investigate").json()["approval"]
    client.post(f"/approvals/{approval['id']}/approve")
    response = client.post(f"/executor/run/{approval['id']}")
    incident = client.get(f"/incidents/{incident_id}").json()
    assert response.status_code == 200
    assert incident["status"] == "resolved"
    assert incident["postmortem"]["summary"]
