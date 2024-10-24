def test_health_endpoint(test_app):
    response = test_app.get('/health')
    assert response.status_code == 200
    assert response.data.decode('utf-8') == 'Healthy'