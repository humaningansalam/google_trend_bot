FROM ubuntu:22.04

WORKDIR /usr/src/app

COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl libglib2.0-0 libnss3 libfontconfig1 libxrender1 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxfixes3\
    && wget -q https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2FLAST_CHANGE?alt=media -O LAST_CHANGE \
    && LATEST=$(cat LAST_CHANGE) \
    && wget https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F${LATEST}%2Fchrome-linux.zip?alt=media -O chrome-linux.zip \
    && unzip chrome-linux.zip \
    && mv chrome-linux /usr/bin/chromium \
    && chmod -R +x /usr/bin/chromium \
    && CHROMIUM_VERSION=$(/usr/bin/chromium/chrome --version | grep -oP 'Chromium \K[0-9]+') \
    && wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION" -O LATEST_RELEASE \
    && CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE) \
    && wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm LAST_CHANGE chrome-linux.zip LATEST_RELEASE chromedriver_linux64.zip \
    && pip3 install --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

CMD ["python3", "main.py"]
