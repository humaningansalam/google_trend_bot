import requests

class SlackSender:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url
        
    def send_message(self, message):
        payload = {"text": message}
        response = requests.post(
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        return response.status_code == 200