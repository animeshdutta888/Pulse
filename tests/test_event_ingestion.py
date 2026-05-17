def test_event_ingestion_creates_incident(client):
    response = client.post(
        "/events/ingest",
        json={
            "service": "checkout-api",
            "kind": "metric",
            "summary": "Latency spike",
            "payload": {"latency_ms": 1800},
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["incident_id"].startswith("inc_")
