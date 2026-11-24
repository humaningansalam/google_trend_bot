from his_mon import BaseMetrics
from prometheus_client import Counter, Summary


class BotMetrics(BaseMetrics):
    def __init__(self) -> None:
        super().__init__(app_name="trends_bot")
        self.rss_poll_duration = Summary(
            "rss_poll_duration_seconds",
            "Time spent polling and processing the Google Trends RSS feed",
            namespace="trends_bot",
        )
        self.completed_rss_polls = Counter(
            "completed_rss_polls_total",
            "Number of RSS polls completed without a delivery failure",
            namespace="trends_bot",
        )
        self.delivered_alerts = Counter(
            "delivered_alerts_total",
            "Number of Google Trends alerts delivered to Slack",
            namespace="trends_bot",
        )


metrics = BotMetrics()
