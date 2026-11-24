import logging
from dataclasses import replace
from datetime import datetime, timedelta
from itertools import count
from threading import Event, Thread
from time import sleep
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pytest
import requests

from src.bot.trend_alert_bot import TrendAlertBot
from src.common.rss_parser import TrendEntry

SEOUL_TIME_ZONE = ZoneInfo("Asia/Seoul")


def test_pruning_releases_only_entries_outside_the_memory_window(
    trend_bot: TrendAlertBot,
    mock_trend_feed: Mock,
    mock_alert_sender: Mock,
    trend_entry: TrendEntry,
):
    now = datetime(2026, 11, 24, 12, 0, tzinfo=SEOUL_TIME_ZONE)
    old_entry = replace(
        trend_entry,
        title="Old Trend",
        observed_at=now - timedelta(days=5),
    )
    recent_entry = replace(
        trend_entry,
        title="Recent Trend",
        observed_at=now - timedelta(days=1),
    )
    mock_trend_feed.parse.return_value = [old_entry, recent_entry]

    trend_bot.poll_trends_once()
    mock_alert_sender.reset_mock()
    trend_bot.prune_seen_trends(now=now)
    trend_bot.poll_trends_once()

    mock_alert_sender.assert_called_once()
    assert mock_alert_sender.call_args.args[0].startswith("Old Trend\n")


def test_poll_suppresses_a_title_already_delivered(
    trend_bot: TrendAlertBot,
    mock_alert_sender: Mock,
):
    trend_bot.poll_trends_once()
    trend_bot.poll_trends_once()

    mock_alert_sender.assert_called_once()


def test_pruning_and_polling_can_run_concurrently(
    trend_bot: TrendAlertBot,
    mock_trend_feed: Mock,
    trend_entry: TrendEntry,
):
    stop_polling = Event()
    title_numbers = count(1)

    def next_entry(_url: str) -> list[TrendEntry]:
        return [
            replace(
                trend_entry,
                title=f"trend-{next(title_numbers)}",
                observed_at=datetime.now(SEOUL_TIME_ZONE),
            )
        ]

    mock_trend_feed.parse.side_effect = next_entry

    def poll_until_stopped() -> None:
        while not stop_polling.is_set():
            trend_bot.poll_trends_once()

    polling_thread = Thread(target=poll_until_stopped, daemon=True)
    polling_thread.start()

    try:
        for _ in range(200):
            trend_bot.prune_seen_trends()
            sleep(0)
    finally:
        stop_polling.set()
        polling_thread.join(timeout=2)

    assert not polling_thread.is_alive()


def test_failed_delivery_is_retried_until_it_succeeds(
    trend_bot: TrendAlertBot,
    mock_alert_sender: Mock,
):
    mock_alert_sender.side_effect = [RuntimeError("Slack API failure"), None]

    trend_bot.poll_trends_once()
    trend_bot.poll_trends_once()
    trend_bot.poll_trends_once()

    assert mock_alert_sender.call_count == 2


def test_slack_http_failure_does_not_mark_the_title_as_delivered(
    mock_trend_feed: Mock,
    monkeypatch: pytest.MonkeyPatch,
):
    failed_response = requests.Response()
    failed_response.status_code = 500
    post = Mock(return_value=failed_response)
    monkeypatch.setattr("src.bot.trend_alert_bot.requests.post", post)
    bot = TrendAlertBot(
        mock_trend_feed,
        poll_interval_minutes=10,
        webhook_url="https://hooks.slack.test/services/example",
    )

    bot.poll_trends_once()
    bot.poll_trends_once()

    assert post.call_count == 2


def test_slack_http_failure_does_not_log_the_webhook_secret(
    mock_trend_feed: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    webhook_url = "https://hooks.slack.test/services/T000/B000/SUPERSECRET"
    failed_response = requests.Response()
    failed_response.status_code = 500
    failed_response.url = webhook_url
    monkeypatch.setattr(
        "src.bot.trend_alert_bot.requests.post",
        Mock(return_value=failed_response),
    )
    bot = TrendAlertBot(
        mock_trend_feed,
        poll_interval_minutes=10,
        webhook_url=webhook_url,
    )

    with caplog.at_level(logging.ERROR, logger="src.bot.trend_alert_bot"):
        bot.poll_trends_once()

    assert webhook_url not in caplog.text
    assert "Slack webhook returned HTTP 500" in caplog.text


def test_slack_transport_failure_does_not_log_the_webhook_secret(
    mock_trend_feed: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    webhook_url = "https://hooks.slack.test/services/T000/B000/SUPERSECRET"
    monkeypatch.setattr(
        "src.bot.trend_alert_bot.requests.post",
        Mock(side_effect=requests.ConnectionError(f"failed: {webhook_url}")),
    )
    bot = TrendAlertBot(
        mock_trend_feed,
        poll_interval_minutes=10,
        webhook_url=webhook_url,
    )

    with caplog.at_level(logging.ERROR, logger="src.bot.trend_alert_bot"):
        bot.poll_trends_once()

    assert webhook_url not in caplog.text
    assert "Slack webhook request failed" in caplog.text


def test_poll_recovers_after_a_feed_error(
    trend_bot: TrendAlertBot,
    mock_trend_feed: Mock,
    mock_alert_sender: Mock,
):
    entries = mock_trend_feed.parse.return_value
    mock_trend_feed.parse.side_effect = [RuntimeError("parser failure"), entries]

    trend_bot.poll_trends_once()
    trend_bot.poll_trends_once()

    mock_alert_sender.assert_called_once()


def test_one_rejected_alert_does_not_block_later_entries(
    trend_bot: TrendAlertBot,
    mock_trend_feed: Mock,
    mock_alert_sender: Mock,
    trend_entry: TrendEntry,
):
    bad_entry = replace(trend_entry, title="Bad Trend")
    good_entry = replace(trend_entry, title="Good Trend")
    mock_trend_feed.parse.return_value = [bad_entry, good_entry]

    def reject_bad_trend(message: str) -> None:
        if message.startswith("Bad Trend\n"):
            raise RuntimeError("payload rejected")

    mock_alert_sender.side_effect = reject_bad_trend

    trend_bot.poll_trends_once()
    trend_bot.poll_trends_once()

    attempted_titles = [
        call.args[0].splitlines()[0] for call in mock_alert_sender.call_args_list
    ]
    assert attempted_titles == ["Bad Trend", "Good Trend", "Bad Trend"]


def test_worker_can_start_and_stop(trend_bot: TrendAlertBot):
    assert not trend_bot.is_active()
    assert trend_bot.start()
    assert trend_bot.is_active()
    assert trend_bot.stop()
    assert not trend_bot.is_active()


def test_start_does_not_create_a_second_worker(trend_bot: TrendAlertBot):
    assert trend_bot.start()
    first_worker = trend_bot.worker_thread

    assert not trend_bot.start()
    assert trend_bot.worker_thread is first_worker


def test_stop_is_idempotent_and_uses_the_configured_timeout(
    trend_bot: TrendAlertBot,
):
    trend_bot.start()
    worker = trend_bot.worker_thread
    assert worker is not None

    with patch.object(worker, "join", wraps=worker.join) as join_mock:
        assert trend_bot.stop()
        assert trend_bot.stop()

    join_mock.assert_called_once_with(timeout=0.1)


def test_timed_out_stop_prevents_a_second_worker(
    mock_trend_feed: Mock,
    mock_alert_sender: Mock,
):
    worker_entered = Event()
    release_worker = Event()
    bot = TrendAlertBot(
        mock_trend_feed,
        poll_interval_minutes=10,
        stop_timeout_seconds=0.01,
        scheduler_check_interval_seconds=0.01,
        alert_sender=mock_alert_sender,
    )
    original_loop = bot._run_scheduler_loop

    def blocked_loop() -> None:
        worker_entered.set()
        release_worker.wait(timeout=1)
        original_loop()

    with patch.object(bot, "_run_scheduler_loop", side_effect=blocked_loop):
        assert bot.start()
        assert worker_entered.wait(timeout=1)
        first_worker = bot.worker_thread
        assert first_worker is not None

        assert not bot.stop()
        assert bot.is_active()
        assert not bot.start()
        assert bot.worker_thread is first_worker

        release_worker.set()
        first_worker.join(timeout=1)
        assert bot.start()
        second_worker = bot.worker_thread
        assert second_worker is not None
        assert second_worker is not first_worker
        assert bot.stop()


def test_concurrent_start_and_stop_calls_keep_one_worker(
    trend_bot: TrendAlertBot,
):
    start_callers = [Thread(target=trend_bot.start) for _ in range(3)]
    for caller in start_callers:
        caller.start()
    for caller in start_callers:
        caller.join(timeout=1)

    first_worker = trend_bot.worker_thread
    assert first_worker is not None

    stop_callers = [Thread(target=trend_bot.stop) for _ in range(3)]
    for caller in stop_callers:
        caller.start()
    for caller in stop_callers:
        caller.join(timeout=1)

    current_worker = trend_bot.worker_thread
    assert current_worker is None or not current_worker.is_alive()
    assert current_worker in {None, first_worker}


@pytest.mark.parametrize(
    ("keyword_arguments", "message"),
    [
        ({"poll_interval_minutes": 0}, "poll_interval_minutes"),
        (
            {
                "poll_interval_minutes": 1,
                "stop_timeout_seconds": -1,
            },
            "stop_timeout_seconds",
        ),
        (
            {
                "poll_interval_minutes": 1,
                "scheduler_check_interval_seconds": 0,
            },
            "scheduler_check_interval_seconds",
        ),
    ],
)
def test_constructor_rejects_invalid_timing_values(
    mock_trend_feed: Mock,
    keyword_arguments: dict[str, float],
    message: str,
):
    with pytest.raises(ValueError, match=message):
        TrendAlertBot(mock_trend_feed, **keyword_arguments)
