from datetime import datetime, timedelta

from pytz import timezone

def test_bot_job(test_bot, mock_rss_parser, mock_slack_sender, mock_flogger):
    test_bot.job()
    
    mock_rss_parser.parse.assert_called_once()
    mock_slack_sender.send_message.assert_called_once()
    mock_flogger.log.assert_called_once()

def test_bot_reset_trend(test_bot):
    seoul_tz = timezone('Asia/Seoul')
    current_time = datetime.now(seoul_tz)
    old_time = current_time - timedelta(days=5)  # 5일 전
    new_time = current_time - timedelta(days=1)  # 1일 전

    test_bot.trend_dict = {
        'Old Trend': old_time,
        'New Trend': new_time
    }
    test_bot.reset_trend()
    assert len(test_bot.trend_dict) == 1
    assert 'New Trend' in test_bot.trend_dict

def test_bot_start_stop(test_bot):
    assert not test_bot.is_running
    test_bot.start()
    assert test_bot.is_running
    test_bot.stop()
    assert not test_bot.is_running