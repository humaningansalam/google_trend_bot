import os
from concurrent.futures import ThreadPoolExecutor

from myapp.src.bot.GoogleTrendsRSSBot import Bot as RSSBot 
from myapp.src.bot.GoogleTrendsScraper import Scraper 
from myapp.comm.fluented_logger import FLogger
from myapp.comm.prometheus_metric import PMetrics
from myapp.comm.rss_parser import RSSParser
from myapp.comm.slack_sender import SlackSender
from myapp.src.monitor import ResourceMonitor
import myapp.comm.tool_util as tool_util

from flask import Flask, request, jsonify, Response
from prometheus_client import generate_latest

def create_app(
    bot = None,
    scraper = None
) -> Flask:
    """Flask 애플리케이션 팩토리 함수"""
    app = Flask(__name__)
    
    # bot과 scraper를 app의 속성으로 저장
    app.bot = bot
    app.scraper = scraper

    @app.route('/start', methods=['POST'])
    def start_bot():
        if not app.bot:
            return jsonify({"status": "Bot not initialized"}), 400
            
        if not app.bot.is_running:
            app.bot.start()
            return jsonify({"status": "Bot started"}), 200
        
        return jsonify({"status": "Bot is already running"}), 400

    @app.route('/stop', methods=['POST'])
    def stop_bot():
        if not app.bot:
            return jsonify({"status": "Bot not initialized"}), 400
            
        if app.bot.is_running:
            app.bot.stop()
            return jsonify({"status": "Bot stopped"}), 200
            
        return jsonify({"status": "Bot is already stopped"}), 400

    @app.route('/reset', methods=['POST'])
    def reset_trend():
        if not app.bot:
            return jsonify({"status": "Bot not initialized"}), 400
            
        app.bot.reset_trend()
        return jsonify({"status": "Trend reset completed"}), 200

    @app.route('/trends', methods=['GET'])
    def get_trends():
        """트렌드 스크랩 동작"""
        if not app.scraper:
            return jsonify({
                "status": "error",
                "message": "Scraper not initialized"
            }), 400
            
        try:
            trends_data = app.scraper.scrape_trends()
            return jsonify({
                "status": "success",
                "data": trends_data
            }), 200
        except Exception as e:
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500

    @app.route('/metrics')
    def metrics_endpoint():
        """Prometheus 메트릭스를 노출하는 엔드포인트"""
        return Response(generate_latest(), mimetype='text/plain')

    @app.route('/health', methods=['GET'])
    def health():
        """health check 엔드포인트"""
        return "Healthy"

    return app

if __name__ == "__main__":
    # 환경 변수 설정
    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    fluentd_url = os.getenv('FLUENTD_URL', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # 로깅 설정
    tool_util.set_logging(log_level)

    # 의존성 객체 생성
    rss_parser = RSSParser()
    slack_sender = SlackSender(bot_url)
    flogger = FLogger(fluentd_url)
    pmetrics = PMetrics()
    
    # Bot 및 Scraper 인스턴스 생성
    bot = RSSBot(rss_parser, slack_sender, flogger, pmetrics, interval)
    scraper = Scraper()
    
    # Flask 앱 생성
    app = create_app(bot=bot, scraper=scraper)
    
    # 리소스 모니터링 시작
    resource_monitor = ResourceMonitor(pmetrics)
    
    # 백그라운드 작업 실행
    executor = ThreadPoolExecutor(max_workers=2)
    executor.submit(resource_monitor.start_monitor)

    # RSSBot 시작
    bot.start()
    
    # Flask 서버 시작
    app.run(host='0.0.0.0', port=5000)