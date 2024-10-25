def test_metrics_endpoint(client):
    response = client.get('/metrics')
    assert response.status_code == 200
    assert response.mimetype == 'text/plain'
    
    # metrics_data = response.data.decode('utf-8')
    
    # # 기본적인 메트릭이 포함되어 있는지 확인
    # assert 'request_processing_seconds' in metrics_data
    # assert 'completed_jobs' in metrics_data
    # assert 'get_trend_data' in metrics_data
    # assert 'errors' in metrics_data
    # assert 'app_cpu_usage' in metrics_data
    # assert 'app_ram_usage' in metrics_data
