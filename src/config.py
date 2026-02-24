#src/config.py

import os

class Config:
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK', None)
    SCHEDULE_INTERVAL = int(os.getenv('SCHEDULE_INTERVAL', "10"))
    
    # 모니터링 설정 (Loki)
    LOKI_URL = os.getenv('LOKI_URL', None)
    LOKI_TAGS = {"app": "trends-bot", "env": "prod"}
    LOG_FILE = "./logs/bot.log"