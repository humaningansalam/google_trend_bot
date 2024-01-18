import requests
import json
import time
import schedule
import os
import logging
from datetime import datetime, timedelta
from pytz import timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

class GoogleTrendsBot:
    def __init__(self, bot_url, interval="10"):
        self.bot_url = bot_url
        self.interval = interval
        self.chrome_options = webdriver.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.trand_list = []
        self.reset_done = False

        # 로그 생성
        logger = logging.getLogger()

        # 로그의 출력 기준 설정
        logger.setLevel(logging.INFO)

        # log 출력 형식
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # log를 console에 출력
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # log를 파일에 출력
        file_handler = logging.FileHandler('GoogleTrendsBot.log')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # 크롬 인스턴스 생성
        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=self.chrome_options)


    def get_now_google_trand(self):
        feed_list = []
        feed_find = []
        day = str(self.server_now.day)+"일"

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

            if len(feed_find) == 0:
                pass
            else:
                for feed in feed_find:
                    title = feed.find_element(By.CLASS_NAME, "title").text
                    if title in self.trand_list:
                        pass
                    else:
                        content = feed.find_element(By.CLASS_NAME, "summary-text").text
                        url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")
                        info = feed.find_element(By.CLASS_NAME, "source-and-time").get_attribute("title")
                        feed_list.append('{} \n{} \n{} \n{}'.format(title, content, url, info))
                        self.trand_list.append(title)

        except Exception as e:   
            logging.error('예외 발생', exc_info=True)
        finally:
            # 현재 창 닫기
            self.browser.close()

        return feed_list

    def send_slack_message(self):
        feed_list = self.get_now_google_trand()

        if len(feed_list) == 0:
            pass
        else:
            for feed in feed_list:
                payload = {
                    "text": feed
                }

                response = requests.post(
                    self.bot_url,
                    data=json.dumps(payload),
                    headers={"Content-Type":"application/json"}
                )

    def reset_trand(self):
        self.trand_list = []

    def job(self):
        if self.now.hour >= 8 and self.now.hour < 24:
            self.send_slack_message()
            self.reset_done = False

    def reset_job(self):
        if self.now.hour == 0:
            if not self.reset_done:
                self.reset_trand()
                self.reset_done = True

    def run(self):
        KST = timezone('Asia/Seoul')

        schedule.every(int(self.interval)).minutes.do(self.job)
        schedule.every().day.at("00:00").do(self.reset_job)

        try:
            while True:
                self.server_now = datetime.now()
                self.now = datetime.now(KST)
                schedule.run_pending()
                time.sleep(10)
        except Exception as e:
            logging.error('예외 발생', exc_info=True)
        finally:
            # WebDriver 세션 종료
            self.browser.quit()

if __name__ == "__main__":
    # 슬랙 웹훅 URL과 스케줄링 간격을 환경 변수에서 가져오도록 변경
    bot_url = os.getenv('SLACK_WEBHOOK', 'default_url')
    interval = os.getenv('SCHEDULE_INTERVAL', "10")
    bot = GoogleTrendsBot(bot_url, interval)
    bot.run()