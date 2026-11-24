import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from threading import Event, Lock, Thread
from typing import Protocol
from zoneinfo import ZoneInfo

import requests
import schedule

from src.common.metrics import metrics
from src.common.rss_parser import TrendEntry

TRENDS_RSS_URL = "https://trends.google.com/trending/rss?geo=KR"
SEOUL_TIME_ZONE = ZoneInfo("Asia/Seoul")
SEEN_TREND_RETENTION = timedelta(days=3)
SLACK_REQUEST_TIMEOUT_SECONDS = 5


class TrendFeed(Protocol):
    def parse(self, url: str) -> list[TrendEntry]: ...


class SlackDeliveryError(RuntimeError):
    pass


class TrendAlertBot:
    def __init__(
        self,
        trend_feed: TrendFeed,
        *,
        poll_interval_minutes: int,
        webhook_url: str | None = None,
        stop_timeout_seconds: float = 5,
        scheduler_check_interval_seconds: float = 10,
        alert_sender: Callable[[str], None] | None = None,
    ) -> None:
        if poll_interval_minutes <= 0:
            raise ValueError("poll_interval_minutes must be positive")
        if stop_timeout_seconds < 0:
            raise ValueError("stop_timeout_seconds must not be negative")
        if scheduler_check_interval_seconds <= 0:
            raise ValueError("scheduler_check_interval_seconds must be positive")

        self._trend_feed = trend_feed
        self._poll_interval_minutes = poll_interval_minutes
        self._stop_timeout_seconds = stop_timeout_seconds
        self._scheduler_check_interval_seconds = scheduler_check_interval_seconds
        self._webhook_url = webhook_url
        self._alert_sender = alert_sender or self._post_slack_message

        self._worker_thread: Thread | None = None
        self._stop_requested = Event()
        self._state_lock = Lock()
        self._trend_lock = Lock()
        self._in_flight_titles: set[str] = set()
        self._seen_at_by_title: dict[str, datetime] = {}
        self._scheduler = schedule.Scheduler()
        self._logger = logging.getLogger(__name__)

    @property
    def worker_thread(self) -> Thread | None:
        with self._state_lock:
            return self._worker_thread

    def is_active(self) -> bool:
        with self._state_lock:
            return self._worker_thread is not None and self._worker_thread.is_alive()

    def poll_trends_once(self) -> None:
        reserved_entries: list[TrendEntry] = []
        with metrics.rss_poll_duration.time():
            try:
                entries = self._trend_feed.parse(TRENDS_RSS_URL)
                reserved_entries = self._reserve_unseen_entries(entries)
            except Exception:
                self._logger.exception("Google Trends RSS poll failed")
                metrics.inc_error("rss_poll_error")
                return

            delivery_failed = False
            for entry in reserved_entries:
                delivered = False
                try:
                    self._alert_sender(self._format_alert(entry))
                    delivered = True
                    metrics.delivered_alerts.inc()
                    self._logger.info(
                        "Delivered trend alert: %s",
                        entry.title,
                        extra={"trend_title": entry.title},
                    )
                except Exception:
                    delivery_failed = True
                    self._logger.exception(
                        "Trend alert delivery failed: %s",
                        entry.title,
                        extra={"trend_title": entry.title},
                    )
                finally:
                    self._finish_delivery(entry, delivered=delivered)

            if delivery_failed:
                metrics.inc_error("alert_delivery_error")
            else:
                metrics.completed_rss_polls.inc()

    def prune_seen_trends(self, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(SEOUL_TIME_ZONE)) - SEEN_TREND_RETENTION
        with self._trend_lock:
            self._seen_at_by_title = {
                title: observed_at
                for title, observed_at in self._seen_at_by_title.items()
                if observed_at > cutoff
            }
            remaining_count = len(self._seen_at_by_title)

        self._logger.info(
            "Pruned trend memory; %s titles remain",
            remaining_count,
        )
        return remaining_count

    def start(self) -> bool:
        with self._state_lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                self._logger.info("Trend alert worker is already running")
                return False

            self._stop_requested.clear()
            self._schedule_tasks()
            worker_thread = Thread(
                target=self._run_scheduler_loop,
                name="google-trends-alert-worker",
                daemon=True,
            )
            self._worker_thread = worker_thread
            worker_thread.start()

        self._logger.info("Trend alert worker started")
        return True

    def stop(self) -> bool:
        with self._state_lock:
            worker_thread = self._worker_thread
            if worker_thread is None or not worker_thread.is_alive():
                self._worker_thread = None
                self._logger.info("Trend alert worker is already stopped")
                return True
            self._stop_requested.set()

        worker_thread.join(timeout=self._stop_timeout_seconds)
        stopped = not worker_thread.is_alive()

        with self._state_lock:
            if stopped and self._worker_thread is worker_thread:
                self._worker_thread = None

        if stopped:
            self._logger.info("Trend alert worker stopped")
        else:
            self._logger.warning("Trend alert worker stop timed out")
        return stopped

    def _post_slack_message(self, message: str) -> None:
        if not self._webhook_url:
            raise SlackDeliveryError("SLACK_WEBHOOK is required to send trend alerts")
        try:
            response = requests.post(
                self._webhook_url,
                json={"text": message},
                timeout=SLACK_REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException:
            raise SlackDeliveryError("Slack webhook request failed") from None
        if not response.ok:
            raise SlackDeliveryError(
                f"Slack webhook returned HTTP {response.status_code}"
            )

    def _schedule_tasks(self) -> None:
        self._scheduler.clear()
        self._scheduler.every(self._poll_interval_minutes).minutes.do(
            self.poll_trends_once
        )
        self._scheduler.every().day.at("00:00").do(self.prune_seen_trends)

    def _run_scheduler_loop(self) -> None:
        while not self._stop_requested.is_set():
            self._scheduler.run_pending()
            self._stop_requested.wait(self._scheduler_check_interval_seconds)

    def _reserve_unseen_entries(
        self,
        entries: list[TrendEntry],
    ) -> list[TrendEntry]:
        reserved_entries: list[TrendEntry] = []
        with self._trend_lock:
            for entry in entries:
                if (
                    entry.title in self._seen_at_by_title
                    or entry.title in self._in_flight_titles
                ):
                    continue
                self._in_flight_titles.add(entry.title)
                reserved_entries.append(entry)
        return reserved_entries

    def _finish_delivery(self, entry: TrendEntry, *, delivered: bool) -> None:
        with self._trend_lock:
            if delivered:
                self._seen_at_by_title[entry.title] = entry.observed_at
            self._in_flight_titles.discard(entry.title)

    @staticmethod
    def _format_alert(entry: TrendEntry) -> str:
        return "\n".join(
            (
                entry.title,
                entry.content,
                entry.link,
                entry.published,
            )
        )
