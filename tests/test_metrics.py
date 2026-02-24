def test_metrics_endpoint(client):
    response = client.get('/metrics')
    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    
    metrics_data = response.data.decode('utf-8')
    
    # 커스텀 메트릭 확인
    assert 'request_processing_seconds' in metrics_data
    assert 'completed_jobs_total' in metrics_data
    assert 'get_trend_data_total' in metrics_data
    
    # 라이브러리 기본 메트릭 확인 (BaseMetrics)
    assert 'trends_bot_cpu_usage_percent' in metrics_data
    assert 'trends_bot_ram_usage_mb' in metrics_data