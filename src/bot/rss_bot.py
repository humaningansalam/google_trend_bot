import logging
import requests
import schedule
import time
from datetime import datetime, timedelta
from threading import Event, Lock, Thread

from pytz import timezone

from src.common.metrics import metrics


class RSSBot:
    def __init__(
        self,
        rss_parser,
        interval,
        stop_timeout=5,
        sleep_interval=10,
        webhook_url=None,
        alert_sender=None,
    ):
        self.rss_parser = rss_parser
        self.interval = int(interval)
        self.stop_timeout = stop_timeout
        self.sleep_interval = sleep_interval
        self.webhook_url = webhook_url
        self.alert_sender = alert_sender or self._send_alert
        self.is_running = False
        self.thread = None
        self._stop_event = Event()
        self._state_lock = Lock()
        self._trend_lock = Lock()
        self._pending_titles = set()
        self._scheduler = schedule.Scheduler()
        self.trend_dict = {}
        self.logger = logging.getLogger("RSSBot")

    def _send_alert(self, message):
        if not self.webhook_url:
            raise ValueError("SLACK_WEBHOOK is required to send trend alerts")
        response = requests.post(
            self.webhook_url,
            json={"text": message},
            timeout=5,
        )
        response.raise_for_status()

    def _register_jobs(self):
        self._scheduler.clear()
        self._scheduler.every(self.interval).minutes.do(self.job)
        self._scheduler.every().day.at("00:00").do(self.reset_trend)

    def _is_worker_alive(self):
        return self.thread is not None and self.thread.is_alive()

    def _sync_runtime_state(self):
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            self.is_running = False

    def is_active(self):
        with self._state_lock:
            self._sync_runtime_state()
            return self._is_worker_alive()

    def job(self):
        new_entries = []
        with metrics.request_time.time():
            try:
                entries = list(
                    self.rss_parser.parse("https://trends.google.com/trending/rss?geo=KR")
                )
                with self._trend_lock:
                    for entry in entries:
                        title = entry["title"]
                        if title in self.trend_dict or title in self._pending_titles:
                            continue
                        self._pending_titles.add(title)
                        new_entries.append(entry)

                for entry in new_entries:
                    message = f"{entry['title']}\n{entry['content']}\n{entry['link']}\n{entry['published']}"
                    try:
                        self.alert_sender(message)
                        with self._trend_lock:
                            self.trend_dict[entry["title"]] = entry["parsed_time"]
                            self._pending_titles.discard(entry["title"])
                            metrics.get_trend_data.inc()
                        self.logger.info(
                            f"Trend Found: {entry['title']}", extra={"trend": entry}
                        )
                    except Exception:
                        with self._trend_lock:
                            self._pending_titles.discard(entry["title"])
                        raise

                metrics.completed_jobs.inc()
            except Exception:
                with self._trend_lock:
                    self._pending_titles.difference_update({entry["title"] for entry in new_entries})
                self.logger.error("Error in job execution", exc_info=True)
                metrics.inc_error("job_execution_error")

    def reset_trend(self):
        current_time = datetime.now(timezone("Asia/Seoul"))
        three_days_ago = current_time - timedelta(days=3)
        with self._trend_lock:
            self.trend_dict = {k: v for k, v in self.trend_dict.items() if v > three_days_ago}
            remaining = len(self.trend_dict)
        self.logger.info(f"Trend reset completed. Items remaining: {remaining}")

    def run(self):
        while not self._stop_event.is_set():
            self._scheduler.run_pending()
            self._stop_event.wait(self.sleep_interval)

    def start(self):
        with self._state_lock:
            self._sync_runtime_state()
            if self._is_worker_alive():
                self.logger.info("Bot is already running")
                return False

            self._stop_event = Event()
            self._scheduler = schedule.Scheduler()
            self._register_jobs()
            self.is_running = True
            self.thread = Thread(target=self.run, daemon=True)
            self.thread.start()
            self.logger.info("Bot started")
            return True

    def stop(self):
        with self._state_lock:
            self._sync_runtime_state()
            thread = self.thread
            if not thread:
                self.is_running = False
                self.logger.info("Bot is not running")
                return True

            self.is_running = False
            self._stop_event.set()

        thread.join(timeout=self.stop_timeout)
        stopped = not thread.is_alive()

        with self._state_lock:
            if stopped and self.thread is thread:
                self.thread = None
            if stopped:
                self.logger.info("Bot stopped")
            else:
                self.is_running = True
                self.logger.warning("Bot stop timed out")
        return stopped
