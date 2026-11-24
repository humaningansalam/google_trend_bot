def test_metrics_endpoint_exposes_service_and_resource_metrics(client):
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"

    metrics_text = response.get_data(as_text=True)
    assert "trends_bot_rss_poll_duration_seconds" in metrics_text
    assert "trends_bot_completed_rss_polls_total" in metrics_text
    assert "trends_bot_delivered_alerts_total" in metrics_text
    assert "trends_bot_cpu_usage_percent" in metrics_text
    assert "trends_bot_ram_usage_mb" in metrics_text
