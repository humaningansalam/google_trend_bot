import os

from bot_.GoogleTrendsRSSBot import Bot as RSSBot 
from comm_.fluented_logger import FLogger
from comm_.prometheus_metric import PMetrics
from comm_.rss_parser import RSSParser
from comm_.slack_sender import SlackSender

import comm_.tool_util as tool_util

from flask import Flask, request, jsonify

from prometheus_flask_exporter import PrometheusMetrics

#flask
app = Flask(__name__)
metrics = PrometheusMetrics(app)

bot = None

@app.route('/start', methods=['GET'])
def start_bot():
    global bot
    if bot:
        bot.start()
        return jsonify({"status": "Bot started"}), 200
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/stop', methods=['GET'])
def stop_bot():
    global bot
    if bot:
        bot.stop()
        return jsonify({"status": "Bot stopped"}), 200
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/reset', methods=['GET'])
def reset_trend():
    global bot
    if bot:
        bot.reset_trend()
        return jsonify({"status": "Trend reset completed"}), 200
    return jsonify({"status": "Bot not initialized"}), 400

@app.route('/health', methods=['GET'])
def health():
    """
    flask health check 
    """
    return "Healthy"

if __name__ == "__main__":

    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    fluentd_url = os.getenv('FLUENTD_URL', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()

    tool_util.set_logging(log_level) 

    rss_parser = RSSParser()
    slack_sender = SlackSender(bot_url)
    flogger = FLogger(fluentd_url)
    pmetrics = PMetrics()

    bot = RSSBot(rss_parser, slack_sender, flogger, pmetrics, interval)

    app.run(host='0.0.0.0', port=5000)