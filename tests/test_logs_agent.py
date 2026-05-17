def test_logs_agent_groups_repeated_errors(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    client.post(f"/incidents/{incident_id}/investigate")
    incident = client.get(f"/incidents/{incident_id}").json()
    logs_finding = incident["findings"][1]
    assert logs_finding["agent"] == "logs"
    assert "repeated" in logs_finding["finding"]
