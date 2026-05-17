def test_context_pack_tracks_token_budget(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    client.post(f"/incidents/{incident_id}/investigate")
    incident = client.get(f"/incidents/{incident_id}").json()
    assert incident["context_pack"]["tokens_estimated"] > 0
    assert incident["context_pack"]["included"]
