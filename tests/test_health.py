def test_health_endpoint_reports_bot_activity(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data.decode("utf-8") == "Healthy"
    assert response.headers["X-Bot-Active"] == "false"

    client.post("/start")
    assert client.get("/health").headers["X-Bot-Active"] == "true"

    client.post("/stop")
    assert client.get("/health").headers["X-Bot-Active"] == "false"
