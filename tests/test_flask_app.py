from unittest.mock import Mock

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.data == b"Healthy"

def test_start_bot(client):
    response = client.post('/start')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'Bot started'

def test_stop_bot(client):
    # First start the bot
    client.post('/start')
    # Then stop it
    response = client.post('/stop')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'Bot stopped'

def test_get_trends(client, test_scraper):
    response = client.get('/trends')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'success'
    assert 'data' in data