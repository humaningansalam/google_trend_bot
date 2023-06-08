# %%
import requests #url로 요청을 보내는 모듈(슬렉)
import json #클라이언트-서버가 통신하는 규율, 규격
import time
import schedule
from datetime import datetime, timedelta
from pytz import timezone

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service

chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument('--headless')
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')


# %%
def get_now_google_trand():
    
    global trand_list
    global server_now
    feed_list = []
    
    day = str(server_now.day)+"일"
    #day = str((dt.datetime.now() - dt.timedelta(days=1)).day)+"일"

    #with webdriver.Chrome() as browser:
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) as browser:

        url = "https://trends.google.co.kr/trends/trendingsearches/daily?geo=KR&hl=ko"
        browser.get(url)

        #time.sleep(1)
        browser.implicitly_wait(10)

        browser = browser.find_elements(By.CLASS_NAME, "feed-list-wrapper")

        for feed in browser: 
            feed_time = (feed.find_element(By.CLASS_NAME, "content-header-title").text).split(" ")[2]
            if feed_time == day:
                feed_find = feed.find_elements(By.CLASS_NAME, "md-list-block")
                break;

        # for feed in browser: 
        #     title = feed.find_element(By.CLASS_NAME, "title").text
        #     url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")
        #     print(title)
        #     print(url)
        
        for feed in feed_find: 
            title = feed.find_element(By.CLASS_NAME, "title").text
            print(title)
            
            if title in trand_list:
                pass
            else:
                content = feed.find_element(By.CLASS_NAME, "summary-text").text
                url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")
                info = feed.find_element(By.CLASS_NAME, "source-and-time").get_attribute("title")
                feed_list.append('{} \n{} \n{} \n{}'.format(title, content, url, info))
                trand_list.append(title)
        
        #print('{} \n{} \n{} \n{}'.format(title, content, url, info))
        #print(list(feed_list))
        return feed_list

# %%
def get_before_google_trand():
    
    global server_now
    feed_list = []
    
    day = str((server_now - timedelta(days=1)).day)+"일"

    #with webdriver.Chrome() as browser:
    with webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options) as browser:

        url = "https://trends.google.co.kr/trends/trendingsearches/daily?geo=KR&hl=ko"
        browser.get(url)

        #time.sleep(1)
        browser.implicitly_wait(10)

        browser = browser.find_elements(By.CLASS_NAME, "feed-list-wrapper")

        for feed in browser: 
            feed_time = (feed.find_element(By.CLASS_NAME, "content-header-title").text).split(" ")[2]
            if feed_time == day:
                feed_find = feed.find_elements(By.CLASS_NAME, "md-list-block")
                break;

        # for feed in browser: 
        #     title = feed.find_element(By.CLASS_NAME, "title").text
        #     url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")
        #     print(title)
        #     print(url)

        for feed in feed_find: 
            title = feed.find_element(By.CLASS_NAME, "title").text
            
            url = feed.find_element(By.TAG_NAME, "feed-item").get_attribute("share-url")

            feed_list.append('{} \n {}'.format(title, url))

        feed_list="\n".join(feed_list)

        #print(feed_find)
        return feed_list

# %%
def send_slack_message(bot_url, day):

    if day == "now":
        feed_list = get_now_google_trand()
    elif day == "before":
        feed_list = get_before_google_trand()
        
    for feed in feed_list:
        payload = {
            "text": feed
        }
        # payload =  { "name" : "Lee Morgan",
        #   "interviewer":"interviewed by: <a href='http://onehungrymind.com/angularjs-dynamic-templates/'>Sonny Stitt</a>",
        #   "day" : "Saturday",
        #   "date": "April 18th", 
        # }
        #get, post => CRUD
        response = requests.post(
            bot_url,
            data=json.dumps(payload),
            headers={"Content-Type":"application/json"}
        )
        print(response)
         
    #print(trand_list)
    #print(feed_list)
    #https://api.slack.com/messaging/composing

# %%
def reset_trand():
    global trand_list
    trand_list = []

# %%
if __name__ == "__main__":

    global trand_list
    global server_now
    trand_list = []

    #dt = datetime.datetime.now(datetime.timezone.utc)
    KST = timezone('Asia/Seoul')
    #dt_korea = dt.astimezone(KST)
    scheduled_time1 = datetime.now().astimezone(KST).replace(hour=8, minute=0, second=0)
    scheduled_time2 = datetime.now().astimezone(KST).replace(hour=23, minute=59, second=0)
    #re_time1 = datetime.strptime("08:00", "%H:%M").time().replace(tzinfo=KST).strftime("%H:%M")
    #re_time2 = datetime.strptime("23:59", "%H:%M").time().replace(tzinfo=KST).strftime("%H:%M")
    #print(dt.hour)
    #print(dt_korea.hour)
    #print(timezone("Asia/Seoul"))
    #print(re_time1)
    #print(re_time2)
    print(scheduled_time1)
    print(scheduled_time2)
    
    #print(datetime.now().year, datetime.now().month, datetime.now().day, 10, 0, 0, tzinfo=KST)
    bot_url = ""

    schedule.every(10).minutes.do(send_slack_message, bot_url, "now").tag("now_send")
    #schedule.every().day.at(scheduled_time1.strftime('%H:%M')).do(send_slack_message, bot_url, "before").tag("before_send")
    schedule.every().day.at(scheduled_time2.strftime('%H:%M')).do(reset_trand).tag("reset")

    while True:
        server_now = datetime.now()
        now = datetime.now(KST)
        #print(now)
        if now.hour >= 8:
            schedule.run_pending()
        time.sleep(10)

    #to = str((dt.datetime.now()).day)+"일"
    #before = str((dt.datetime.now() - dt.timedelta(days=1)).day)+"일"
    #print(to)
    #print(before)
    #send_slack_message()
    #get_now_google_trand()
    #get_before_google_trand()

# %%



