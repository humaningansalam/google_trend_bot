import requests
import json
import time
import schedule
import os
import logging
from datetime import datetime, timedelta
from pytz import timezone

from fluent import sender
from fluent import event
from prometheus_client import start_http_server, Summary, Counter

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromiumService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

class GoogleTrendsBot:
    def __init__(self, bot_url, fluentd_url, log_level, interval="10"):
        self.bot_url = bot_url
        self.interval = interval
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.trend_list = []
        self.reset_done = False

        # 로그 생성
        logger = logging.getLogger()
        # 로그 레벨 문자열을 적절한 로깅 상수로 변환
        log_level_constant = getattr(logging, log_level, logging.INFO)
        # 로그의 출력 기준 설정
        logger.setLevel(log_level_constant)
        # log 출력 형식
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # log를 console에 출력
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
        # log를 파일에 출력
        #file_handler = logging.FileHandler('GoogleTrendsBot.log')
        #file_handler.setFormatter(formatter)
        #logger.addHandler(file_handler)

        # Fluentd 로거 생성
        self.fluent = sender.FluentSender('crawling', host=fluentd_url, port=24224)

        # Prometheus 메트릭 정의
        self.REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
        self.COMPLETED_JOBS = Counter('completed_jobs', 'Number of completed jobs')
        self.GET_TREND_DATA = Counter('get_trend_data', 'Number of get trend data')
        self.CRAWLING_TREND_DATA = Counter('crawling_trend_data', 'Number of crawling trend data')
        self.ERRORS = Counter('errors', 'Number of errors')

        # 크롬 인스턴스 생성
        self.browser = webdriver.Chrome(service=ChromiumService('/usr/bin/chromedriver'), options=self.chrome_options)


    def get_now_google_trend(self):
        feed_list = []
        feed_find = []
        day = str(self.now.day)+"일"

        # WebDriver 세션이 유효한지 확인
        if self.browser.service.is_connectable() is False:
            # WebDriver 세션이 유효하지 않으면 새로 생성
            self.browser = webdriver.Chrome(service=ChromiumService('/usr/bin/chromedriver'), options=self.chrome_options)
            logging.debug('reopen webdriver session')

        try:
            url = "https://trends.google.co.kr/trends/trendingsearches/daily?geo=KR&hl=ko"
            self.browser.get(url)
            self.browser.implicitly_wait(60)
            browser = self.browser.find_elements(By.CLASS_NAME, "feed-list-wrapper")

            for feed in browser: 
                feed_time = (feed.find_element(By.CLASS_NAME, "content-header-title").text).split(" ")[2]
                if feed_time == day:
                    feed_find = feed.find_elements(By.CLASS_NAME, "md-list-block")
                    break;

            logging.debug(len(feed_find))
            if len(feed_find) == 0:
                pass
            else:
                for feed in feed_find:
                    title = feed.find_element(By.CLASS_NAME, "title").text
                    if title in self.trend_list:
                        pass
                    else:
                        content = feed.find_element(By.CLASS_NAME, "summary-text").text
                        url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")
                        info = feed.find_element(By.CLASS_NAME, "source-and-time").get_attribute("title")
                        feed_list.append('{} \n{} \n{} \n{}'.format(title, content, url, info))

                        logging.debug(title)

                        self.trend_list.append(title)
                        self.CRAWLING_TREND_DATA.inc()

        except Exception as e:
            self.ERRORS.inc()   
            logging.error('예외 발생', exc_info=True)
            self.browser.quit()


        return feed_list

    def send_slack_message(self):

        # 작업 수행 시간 측정 시작
        with self.REQUEST_TIME.time():
            feed_list = self.get_now_google_trend()

            if len(feed_list) == 0:
                pass
            else:
                for feed in feed_list:
                    payload = {
                        "text": feed
                    }

                    # Fluentd로 전송
                    self.fluent.emit_with_time('follow', int(time.time()), payload)

                    # Slack로 전송
                    response = requests.post(
                        self.bot_url,
                        data=json.dumps(payload),
                        headers={"Content-Type":"application/json"}
                    )
                    self.GET_TREND_DATA.inc()

            # 완료된 작업 수 증가
            self.COMPLETED_JOBS.inc()

    def reset_trend(self):
        self.trend_list = []
        logging.info('reset done')

    def job(self):
        if self.now.hour >= 8 and self.now.hour < 24:
            self.send_slack_message()
            if self.reset_done:
                self.reset_done = False

    def reset_job(self):
        if not self.reset_done:
            self.reset_trend()
            self.reset_done = True

    def run(self):
        KST = timezone('Asia/Seoul')

        schedule.every(int(self.interval)).minutes.do(self.job)
        schedule.every().day.at("01:00").do(self.reset_job)

        try:
            while True:
                self.now = datetime.now(KST)
                schedule.run_pending()
                time.sleep(10)
        except Exception as e:
            self.ERRORS.inc()
            logging.error('예외 발생', exc_info=True)
        finally:
            # WebDriver 세션 종료
            self.browser.quit()

if __name__ == "__main__":
    # 슬랙 웹훅 URL과 스케줄링 간격을 환경 변수에서 가져오도록 변경
    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    fluentd_url = os.getenv('FLUENTD_URL', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    start_http_server(8000)

    bot = GoogleTrendsBot(bot_url, fluentd_url, log_level, interval)
    bot.run()
