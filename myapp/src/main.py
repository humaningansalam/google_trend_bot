import os
from concurrent.futures import ThreadPoolExecutor

from myapp.src.bot.GoogleTrendsRSSBot import Bot as RSSBot 
from myapp.comm.fluented_logger import FLogger
from myapp.comm.prometheus_metric import PMetrics
from myapp.comm.rss_parser import RSSParser
from myapp.comm.slack_sender import SlackSender
from myapp.src.monitor import ResourceMonitor

import comm_.tool_util as tool_util

from flask import Flask, request, jsonify

app = Flask(__name__)

bot = None

@app.route('/start', methods=['POST'])
def start_bot():
    global bot
    if bot and not bot.is_running:
        bot.start()
        return jsonify({"status": "Bot started"}), 200
    elif bot and bot.is_running:
        return jsonify({"status": "Bot is already running"}), 400
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/stop', methods=['POST'])
def stop_bot():
    global bot
    if bot and bot.is_running:
        bot.stop()
        return jsonify({"status": "Bot stopped"}), 200
    elif bot and not bot.is_running:
        return jsonify({"status": "Bot is already stopped"}), 400
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/reset', methods=['POST'])
def reset_trend():
    global bot
    if bot:
        bot.reset_trend()
        return jsonify({"status": "Trend reset completed"}), 200
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/health', methods=['GET'])
def health():
    return "Healthy"

if __name__ == "__main__":
    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    fluentd_url = os.getenv('FLUENTD_URL', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    tool_util.set_logging(log_level)

    # Dependency injection for Bot class
    rss_parser = RSSParser()
    slack_sender = SlackSender(bot_url)
    flogger = FLogger(fluentd_url)
    pmetrics = PMetrics()

    bot = RSSBot(rss_parser, slack_sender, flogger, pmetrics, interval)
    resource_monitor = ResourceMonitor(pmetrics)

    executor = ThreadPoolExecutor(max_workers=2)
    executor.submit(resource_monitor.start_monitor)

    app.run(host='0.0.0.0', port=5000)#flask