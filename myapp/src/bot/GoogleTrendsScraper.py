import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains

class Scraper:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        
    def setup_driver(self):
        return webdriver.Chrome(options=self.chrome_options)
        
    def scrape_trends(self):
        driver = self.setup_driver()
        try:
            driver.get("https://trends.google.co.kr/trending?geo=KR&hl=ko&hours=24")
            data = self._scrape_data(driver)
            return data
        finally:
            driver.quit()
            
    def _scrape_data(self, driver):
        data = []
        tr_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//tbody[@jsname='cC57zf']/tr[@jsname='oKdM2c']"))
        )
        
        for tr in tr_elements:
            ActionChains(driver).move_to_element(tr).perform()
            tr.click()
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "EMz5P"))
            )
            time.sleep(0.5)

            trend_data = self._extract_trend_data(tr, driver)
            data.append(trend_data)
            
        return data
        
    def _extract_trend_data(self, tr, driver):
        trend_title = tr.find_element(By.CLASS_NAME, "mZ3RIc").text
        search_volume = tr.find_element(By.CLASS_NAME, "lqv0Cb").text
        
        try:
            status_text = tr.find_element(By.CLASS_NAME, "UQMqQd").text
            active_status = status_text if "활성" not in status_text else "N/A"
        except:
            active_status = "N/A"
            
        try:
            emz5p_element = driver.find_element(By.CLASS_NAME, "EMz5P")
            analysis_spans = emz5p_element.find_elements(
                By.XPATH, ".//div[@class='HLcRPe']//span[@jsname='V67aGc']"
            )
            trend_analysis = [span.text for span in analysis_spans if span.text.strip()]
        except:
            trend_analysis = []
            
        try:
            news_data = self._extract_news_data(emz5p_element)
        except:
            news_data = []
            
        return {
            "트렌드 제목": trend_title,
            "검색량": search_volume,
            "트렌드 분석": trend_analysis,
            "뉴스 데이터": news_data,
            "활성 상태": active_status
        }
        
    def _extract_news_data(self, emz5p_element):
        news_data = []
        news_elements = emz5p_element.find_elements(
            By.XPATH, ".//div[@jsaction='click:vx9mmb;contextmenu:rbJKIe']"
        )
        for news in news_elements:
            try:
                news_title = news.find_element(By.CLASS_NAME, "QbLC8c").text
                news_url = news.find_element(By.TAG_NAME, "a").get_attribute("href")
                news_data.append({"뉴스 제목": news_title, "URL": news_url})
            except:
                continue
        return news_data