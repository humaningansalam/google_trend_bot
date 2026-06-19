from datetime import datetime, timedelta
from threading import Barrier, Event, Thread
from unittest.mock import Mock, patch

from pytz import timezone


def test_bot_job(test_bot, mock_rss_parser, mock_send_alert):
    test_bot.job()

    mock_rss_parser.parse.assert_called_once()
    mock_send_alert.assert_called()


def test_bot_reset_trend(test_bot):
    seoul_tz = timezone("Asia/Seoul")
    current_time = datetime.now(seoul_tz)
    old_time = current_time - timedelta(days=5)
    new_time = current_time - timedelta(days=1)

    test_bot.trend_dict = {
        "Old Trend": old_time,
        "New Trend": new_time,
    }
    test_bot.reset_trend()
    assert len(test_bot.trend_dict) == 1
    assert "New Trend" in test_bot.trend_dict


def test_bot_start_stop(test_bot):
    assert not test_bot.is_running
    assert test_bot.start()
    assert test_bot.is_running
    test_bot.stop()
    assert not test_bot.is_running


def test_bot_start_is_idempotent(test_bot):
    test_bot.start()
    first_thread = test_bot.thread
    test_bot.start()
    assert test_bot.thread is first_thread
    test_bot.stop()


def test_bot_stop_is_idempotent_and_bounded(test_bot):
    test_bot.start()
    with patch.object(test_bot.thread, "join", wraps=test_bot.thread.join) as join_mock:
        test_bot.stop()
        test_bot.stop()
    join_mock.assert_called_once_with(timeout=0.1)


def test_bot_stop_timeout_keeps_single_worker_until_old_thread_exits(test_bot):
    start_gate = Event()
    release_gate = Event()
    original_run = test_bot.run

    def blocked_run():
        start_gate.set()
        release_gate.wait(timeout=1)
        original_run()

    with patch.object(test_bot, "run", side_effect=blocked_run):
        assert test_bot.start()
        assert start_gate.wait(timeout=1)
        first_thread = test_bot.thread

        test_bot.stop_timeout = 0.01
        assert not test_bot.stop()
        assert test_bot.is_running
        assert test_bot.thread is first_thread

        assert not test_bot.start()
        assert test_bot.thread is first_thread

        release_gate.set()
        first_thread.join(timeout=1)
        assert test_bot.start()
        second_thread = test_bot.thread
        assert second_thread is not None and second_thread is not first_thread
        test_bot.stop()


def test_bot_start_and_stop_from_multiple_callers_stay_single_thread(test_bot):
    start_threads = []
    stop_threads = []

    for _ in range(3):
        thread = Thread(target=test_bot.start)
        thread.start()
        start_threads.append(thread)

    for thread in start_threads:
        thread.join(timeout=1)

    first_thread = test_bot.thread
    assert first_thread is not None

    for _ in range(3):
        thread = Thread(target=test_bot.stop)
        thread.start()
        stop_threads.append(thread)

    for thread in stop_threads:
        thread.join(timeout=1)

    assert test_bot.thread is None or not test_bot.thread.is_alive()
    assert first_thread is not None
    assert test_bot.thread in {None, first_thread}


def test_bot_instances_do_not_share_scheduler_jobs(test_bot, mock_rss_parser, mock_send_alert):
    second_bot = test_bot.__class__(
        rss_parser=mock_rss_parser,
        interval=10,
        stop_timeout=0.1,
        sleep_interval=0.01,
    )
    try:
        assert test_bot.start()
        assert second_bot.start()

        assert len(test_bot._scheduler.jobs) == 2
        assert len(second_bot._scheduler.jobs) == 2
        assert test_bot._scheduler is not second_bot._scheduler
    finally:
        test_bot.stop()
        second_bot.stop()


def test_bot_stop_timeout_does_not_duplicate_jobs_on_restart(test_bot):
    start_gate = Barrier(2)
    release_gate = Event()
    original_run = test_bot.run

    def blocked_run():
        start_gate.wait(timeout=1)
        release_gate.wait(timeout=1)
        original_run()

    with patch.object(test_bot, "run", side_effect=blocked_run):
        assert test_bot.start()
        start_gate.wait(timeout=1)
        first_thread = test_bot.thread
        test_bot.stop_timeout = 0.01
        assert not test_bot.stop()
        assert not test_bot.start()
        assert len(test_bot._scheduler.jobs) == 2
        assert test_bot.thread is first_thread

        release_gate.set()
        first_thread.join(timeout=1)
        assert test_bot.start()
        assert len(test_bot._scheduler.jobs) == 2
        assert test_bot.thread is not None and test_bot.thread is not first_thread
        test_bot.stop()
