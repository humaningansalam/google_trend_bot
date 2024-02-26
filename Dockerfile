FROM alpine:latest

WORKDIR /usr/src/app

COPY . .

RUN apk add --no-cache python3 py3-pip chromium udev ttf-freefont \
    && CHROMIUM_VERSION=$(chromium-browser --version | grep -oP 'Chromium \K[0-9]+') \
    && wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION" -O LATEST_RELEASE \
    && CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE) \
    && wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm LATEST_RELEASE chromedriver_linux64.zip \
    && python3 -m pip install --upgrade pip \
    && python3 pip install --no-cache-dir -r requirements.txt

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL = INFO

CMD ["python3", "main.py"]