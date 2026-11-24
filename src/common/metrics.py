from his_mon import BaseMetrics
from prometheus_client import Counter, Summary


class BotMetrics(BaseMetrics):
    def __init__(self) -> None:
        super().__init__(app_name="trends_bot")
        self.rss_poll_duration = Summary(
            "request_processing_seconds",
            "Time spent polling and processing the Google Trends RSS feed",
        )
        self.completed_rss_polls = Counter(
            "completed_jobs_total",
            "Number of RSS polls completed without a delivery failure",
        )
        self.delivered_alerts = Counter(
            "get_trend_data_total",
            "Number of Google Trends alerts delivered to Slack",
        )


metrics = BotMetrics()
