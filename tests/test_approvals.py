def test_executor_requires_approval(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    approval = client.post(f"/incidents/{incident_id}/investigate").json()["approval"]
    response = client.post(f"/executor/run/{approval['id']}")
    assert response.status_code == 400
    assert "Approval required" in response.json()["detail"]
