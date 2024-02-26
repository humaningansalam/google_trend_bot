FROM python:3.10.13-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
    && apt-get install -y wget gnupg chromium\
    && CHROMIUM_VERSION=$(chromium --version | grep -oP 'Chromium \K[0-9]+') \
    && wget -q "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROMIUM_VERSION" -O LATEST_RELEASE \
    && CHROMEDRIVER_VERSION=$(cat LATEST_RELEASE) \
    && wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip" \
    && unzip chromedriver_linux64.zip \
    && mv chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    && rm LATEST_RELEASE chromedriver_linux64.zip \
    && python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL = INFO

CMD ["python", "main.py"]