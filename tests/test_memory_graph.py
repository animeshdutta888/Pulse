def test_memory_graph_updates_after_resolution(client):
    incident_id = client.get("/demo/seed").json()["incident_id"]
    approval = client.post(f"/incidents/{incident_id}/investigate").json()["approval"]
    client.post(f"/approvals/{approval['id']}/approve")
    client.post(f"/executor/run/{approval['id']}")
    graph = client.get("/memory/graph").json()
    assert graph["nodes"]
    assert any(edge["kind"] == "fixed_by" for edge in graph["edges"])
