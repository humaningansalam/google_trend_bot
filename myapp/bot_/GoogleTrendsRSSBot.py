import schedule
from threading import Thread
import time
from datetime import datetime, timedelta
from pytz import timezone
import logging

class Bot:
    def __init__(self, rss_parser, slack_sender, flogger, pmetrics, interval):
        self.rss_parser = rss_parser
        self.slack_sender = slack_sender
        self.flogger = flogger
        self.pmetrics = pmetrics
        self.interval = int(interval)
        self.is_running = False
        self.thread = None
        self.trend_dict = {}

        self.start()

    def job(self):
        with self.pmetrics.request_time.time():
            try:
                entries = self.rss_parser.parse("https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR")
                for entry in entries:
                    if entry['title'] not in self.trend_dict:
                        message = f"{entry['title']}\n{entry['content']}\n{entry['link']}\n{entry['published']}"
                        if self.slack_sender.send_message(message):
                            self.flogger.log('trend', entry)
                            self.trend_dict[entry['title']] = entry['parsed_time']
                            self.pmetrics.get_trend_data.inc()
                self.pmetrics.completed_jobs.inc()
            except Exception as e:
                logging.error('Error in job execution', exc_info=True)
                self.pmetrics.errors.inc()

    def reset_trend(self):
        current_time = datetime.now(timezone('Asia/Seoul'))
        three_days_ago = current_time - timedelta(days=3)
        self.trend_dict = {k: v for k, v in self.trend_dict.items() if v > three_days_ago}
        logging.info('Trend reset completed. Items remaining: %d', len(self.trend_dict))

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
            logging.info("Bot started")
        else:
            logging.info("Bot is already running")

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.thread.join()
            logging.info("Bot stopped")
        else:
            logging.info("Bot is not running")