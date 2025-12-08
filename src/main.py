#src/main.py

from flask import Flask, jsonify, Response
from prometheus_client import generate_latest

# 모듈 임포트
from src.bot.rss_bot import RSSBot
from src.bot.scraper import Scraper
from src.common.rss_parser import RSSParser
from src.config import Config
from src.common.metrics import metrics

# 라이브러리 활용
from his_mon import setup_logging, ResourceMonitor, init_webhook

def create_app(bot=None, scraper=None):
    app = Flask(__name__)
    app.bot = bot
    app.scraper = scraper

    @app.route('/start', methods=['POST'])
    def start_bot():
        if not app.bot: return jsonify({"status": "Bot not initialized"}), 400
        if not app.bot.is_running:
            app.bot.start()
            return jsonify({"status": "Bot started"}), 200
        return jsonify({"status": "Bot is already running"}), 400

    @app.route('/stop', methods=['POST'])
    def stop_bot():
        if not app.bot: return jsonify({"status": "Bot not initialized"}), 400
        if app.bot.is_running:
            app.bot.stop()
            return jsonify({"status": "Bot stopped"}), 200
        return jsonify({"status": "Bot is already stopped"}), 400

    @app.route('/reset', methods=['POST'])
    def reset_trend():
        if not app.bot: return jsonify({"status": "Bot not initialized"}), 400
        app.bot.reset_trend()
        return jsonify({"status": "Trend reset completed"}), 200

    @app.route('/trends', methods=['GET'])
    async def get_trends():
        if not app.scraper: return jsonify({"status": "error", "message": "Scraper not initialized"}), 400
        try:
            trends_data = await app.scraper.scrape_trends()
            return jsonify({"status": "success", "data": trends_data}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/metrics')
    def metrics_endpoint():
        return Response(generate_latest(), mimetype='text/plain')

    @app.route('/health')
    def health():
        return "Healthy"

    return app

if __name__ == "__main__":
    # 1. 로깅 & 웹훅 설정
    init_webhook(url=Config.SLACK_WEBHOOK)
    setup_logging(
        level=Config.LOG_LEVEL,
        loki_url=Config.LOKI_URL,
        tags=Config.LOKI_TAGS,
        log_file=Config.LOG_FILE
    )

    # 2. 봇 생성
    rss_parser = RSSParser()
    bot = RSSBot(rss_parser, interval=Config.SCHEDULE_INTERVAL)
    scraper = Scraper()
    
    app = create_app(bot=bot, scraper=scraper)
    
    # 3. 리소스 모니터 시작
    monitor = ResourceMonitor(metrics_obj=metrics, interval=5)
    monitor.start()

    # 4. 실행
    bot.start()
    app.run(host='0.0.0.0', port=5000)