

def test_health_check(test_app):
    with test_app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        assert response.data == b"Healthy"

def test_start_bot(test_app):
    with test_app.test_client() as client:
        response = client.post('/start')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'Bot started'

def test_stop_bot(test_app):
    with test_app.test_client() as client:
        # First start the bot
        client.post('/start')
        # Then stop it
        response = client.post('/stop')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'Bot stopped'

def test_get_trends(test_app, test_scraper):
    with test_app.test_client() as client:
        response = client.get('/trends')
        assert response.status_code == 200
        data = response.get_json()
        assert data['status'] == 'success'
        assert 'data' in data