#src/bot/rss_bot.py

import schedule
import time
import logging
from threading import Thread
from datetime import datetime, timedelta
from pytz import timezone

from his_mon import send_alert
from src.common.metrics import metrics

class RSSBot:
    def __init__(self, rss_parser, interval):
        self.rss_parser = rss_parser
        self.interval = int(interval)
        self.is_running = False
        self.thread = None
        self.trend_dict = {}
        self.logger = logging.getLogger("RSSBot")

    def job(self):
        with metrics.request_time.time():
            try:
                entries = self.rss_parser.parse("https://trends.google.com/trending/rss?geo=KR")
                for entry in entries:
                    if entry['title'] not in self.trend_dict:
                        message = f"{entry['title']}\n{entry['content']}\n{entry['link']}\n{entry['published']}"
                        
                        send_alert(message)
                        
                        self.logger.info(f"Trend Found: {entry['title']}", extra={"trend": entry})
                        self.trend_dict[entry['title']] = entry['parsed_time']
                        metrics.get_trend_data.inc()
                            
                metrics.completed_jobs.inc()
            except Exception as e:
                self.logger.error('Error in job execution', exc_info=True)
                metrics.inc_error('job_execution_error')

    def reset_trend(self):
        current_time = datetime.now(timezone('Asia/Seoul'))
        three_days_ago = current_time - timedelta(days=3)
        self.trend_dict = {k: v for k, v in self.trend_dict.items() if v > three_days_ago}
        self.logger.info(f'Trend reset completed. Items remaining: {len(self.trend_dict)}')

    def run(self):
        schedule.every(self.interval).minutes.do(self.job)
        schedule.every().day.at("00:00").do(self.reset_trend)
        while self.is_running:
            schedule.run_pending()
            time.sleep(10)

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = Thread(target=self.run)
            self.thread.start()
            self.logger.info("Bot started")
        else:
            self.logger.info("Bot is already running")

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.thread.join()
            self.logger.info("Bot stopped")
        else:
            self.logger.info("Bot is not running")