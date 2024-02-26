FROM ubuntu:22.04

WORKDIR /usr/src/app

COPY . .

RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip wget unzip \
    && wget -q https://raw.githubusercontent.com/scheib/chromium-latest-linux/master/update.sh \
    && chmod +x update.sh \
    && ./update.sh \
    && CHROMIUM_VERSION=$(chromium --version | grep -oP 'Chromium \K[0-9]+') \
    && wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION" -O LATEST_RELEASE \
    && CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE) \
    && wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm update.sh LATEST_RELEASE chromedriver_linux64.zip \
    && pip3 install --upgrade pip \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

CMD ["python3", "main.py"]
