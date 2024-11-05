import time
import pandas as pd
from playwright.sync_api import sync_playwright
class Scraper:
    def __init__(self):
        pass
        
    def setup_browser(self, playwright):
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        return browser, context
        
    def scrape_trends(self):
        with sync_playwright() as playwright:
            browser, context = self.setup_browser(playwright)
            try:
                page = context.new_page()
                page.goto("https://trends.google.co.kr/trending?geo=KR&hl=ko&hours=24")
                # 페이지 로딩 대기
                page.wait_for_selector("tbody[jsname='cC57zf']")
                data = self._scrape_data(page)
                return data
            finally:
                browser.close()
                
    def _scrape_data(self, page):
        data = []
        while True:
            tr_count = 0
            # 데이터 추출
            tr_elements = page.query_selector_all("tbody[jsname='cC57zf'] tr[jsname='oKdM2c']")
            
            for tr in tr_elements:
                tr.click()
                # 클릭 후 상세 정보가 로드될 때까지 대기
                page.wait_for_selector(".EMz5P", timeout=10000)
                time.sleep(0.5)  # 데이터 로드를 위한 짧은 대기
                trend_data = self._extract_trend_data(tr, page)
                data.append(trend_data)
                tr_count += 1

            # 데이터가 25개 미만이면 "다음" 버튼 클릭
            if tr_count >= 25:
                try:
                    next_button = page.query_selector("button[jsname='ViaHrd']")
                    if next_button:
                        next_button.click()
                        time.sleep(1)  # 버튼 클릭 후 로딩 대기
                    else:
                        break  # 버튼이 없으면 종료
                except Exception:
                    break  # 예외 발생 시 종료
            else:
                break  # 데이터가 25개 이상이면 종료

        return data

        
    def _extract_trend_data(self, tr, page):
        trend_title = tr.query_selector(".mZ3RIc").inner_text()
        search_volume = tr.query_selector(".lqv0Cb").inner_text()
        
        try:
            status_element = tr.query_selector(".UQMqQd")
            active_status = status_element.inner_text() if status_element else "N/A"
            if "활성" in active_status:
                active_status = "N/A"
        except:
            active_status = "N/A"
            
        try:
            emz5p_element = page.query_selector(".EMz5P")
            analysis_elements = emz5p_element.query_selector_all("div.HLcRPe span[jsname='V67aGc']")
            trend_analysis = [element.inner_text() for element in analysis_elements if element.inner_text().strip()]
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
        news_elements = emz5p_element.query_selector_all(
            "div[jsaction='click:vx9mmb;contextmenu:rbJKIe']"
        )
        
        for news in news_elements:
            try:
                news_title = news.query_selector(".QbLC8c").inner_text()
                news_url = news.query_selector("a").get_attribute("href")
                news_data.append({"뉴스 제목": news_title, "URL": news_url})
            except:
                continue
                
        return news_data

if __name__ == "__main__":
    app = Scraper()

    trends_data = app.scrape_trends()
    print(trends_data)