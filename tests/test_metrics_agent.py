def test_metrics_agent_finding_is_recorded(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    client.post(f"/incidents/{incident_id}/investigate")
    incident = client.get(f"/incidents/{incident_id}").json()
    metrics_finding = incident["findings"][0]
    assert metrics_finding["agent"] == "metrics"
    assert "latency increased" in metrics_finding["finding"]
