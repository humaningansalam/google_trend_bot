FROM ubuntu:22.04

WORKDIR /usr/src/app

COPY . .

RUN apt-get update
RUN apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl libglib2.0-0 libnss3 libfontconfig1 libxrender1 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango1.0-0 libasound2
RUN wget -q https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2FLAST_CHANGE?alt=media -O LAST_CHANGE && \
    echo $(cat LAST_CHANGE) > latest && \
    export LATEST=$(cat latest) && \
    wget https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F${LATEST}%2Fchrome
RUN unzip chrome-linux.zip
RUN mv chrome-linux /usr/bin/chromium
RUN chmod -R +x /usr/bin/chromium
RUN CHROMI_VERSION=$(/usr/bin/chromium/chrome --version | grep -oP 'ChromiumK[0-9]+')
RUN wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION" -O LATEST_RELEASE
RUN CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE)
RUN wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
RUN unzip chromedriver_linux64.zip
RUN mv chromedriver /usr/bin/chromedriver
RUN chmod +x /usr/bin/chromedriver
RUN rm LAST_CHANGE chrome-linux.zip LATEST_RELEASE chromedriver_linux64.zip
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*


WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

CMD ["python3", "main.py"]
