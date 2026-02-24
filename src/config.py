#src/config.py

import os

class Config:
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK', None)
    SCHEDULE_INTERVAL = int(os.getenv('SCHEDULE_INTERVAL', "10"))
    
    # 모니터링 설정 (Loki)
    LOKI_URL = os.getenv('LOKI_URL', None)
    LOKI_TAGS = {
        "app": os.getenv("APP_NAME", "trends-bot"),
        "env": os.getenv("APP_ENV", "dev")
    }
    LOG_FILE = "./logs/bot.log"