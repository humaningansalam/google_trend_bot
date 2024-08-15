import requests
import json
import time
import schedule
import os
import logging
from datetime import datetime, timedelta
from pytz import timezone

from fluent import sender
from fluent import event
from prometheus_client import start_http_server, Summary, Counter

import feedparser

class GoogleTrendsBot:
    def __init__(self, bot_url, fluentd_url, log_level, interval="10"):
        self.bot_url = bot_url
        self.interval = interval
        self.trend_dict = {}  # 키: 제목, 값: 추가된 시간

        # 로그 설정
        logger = logging.getLogger()
        log_level_constant = getattr(logging, log_level, logging.INFO)
        logger.setLevel(log_level_constant)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # Fluentd 로거 생성
        self.fluent = sender.FluentSender('crawling', host=fluentd_url, port=24224)

        # Prometheus 메트릭 정의
        self.REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
        self.COMPLETED_JOBS = Counter('completed_jobs', 'Number of completed jobs')
        self.GET_TREND_DATA = Counter('get_trend_data', 'Number of get trend data')
        self.ERRORS = Counter('errors', 'Number of errors')

    def get_now_google_trend(self):
        feed_list = []
        url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"

        try:
            feed = feedparser.parse(url)
            current_time = datetime.now(timezone('Asia/Seoul'))
            for entry in feed.entries:
                title = entry.title
                if title not in self.trend_dict:
                    content = entry.description
                    link = entry.link
                    published = entry.published
                    feed_list.append(f"{title}\n{content}\n{link}\n{published}")
                    self.trend_dict[title] = current_time
                    self.GET_TREND_DATA.inc()

        except Exception as e:
            self.ERRORS.inc()
            logging.error('예외 발생', exc_info=True)

        return feed_list

    def send_slack_message(self):
        with self.REQUEST_TIME.time():
            feed_list = self.get_now_google_trend()

            if feed_list:
                for feed in feed_list:
                    payload = {
                        "text": feed
                    }

                    # Fluentd로 전송
                    self.fluent.emit_with_time('follow', int(time.time()), payload)

                    # Slack로 전송
                    response = requests.post(
                        self.bot_url,
                        data=json.dumps(payload),
                        headers={"Content-Type":"application/json"}
                    )

            self.COMPLETED_JOBS.inc()

    def reset_trend(self):
        current_time = datetime.now(timezone('Asia/Seoul'))
        three_days_ago = current_time - timedelta(days=3)
        self.trend_dict = {k: v for k, v in self.trend_dict.items() if v > three_days_ago}
        logging.info('Trend reset completed. Items remaining: %d', len(self.trend_dict))

    def job(self):
        self.send_slack_message()

    def run(self):
        schedule.every(int(self.interval)).minutes.do(self.job)
        schedule.every().day.at("00:00").do(self.reset_trend)  # 매일 자정에 reset_trend 실행

        try:
            while True:
                schedule.run_pending()
                time.sleep(10)
        except Exception as e:
            self.ERRORS.inc()
            logging.error('예외 발생', exc_info=True)

if __name__ == "__main__":
    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    fluentd_url = os.getenv('FLUENTD_URL', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    start_http_server(8000)

    bot = GoogleTrendsBot(bot_url, fluentd_url, log_level, interval)
    bot.run()