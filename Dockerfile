FROM python:3.10.13-slim

WORKDIR /usr/src/app

COPY . .

RUN export ARCHITECTURE=$(uname -m); \
    if [ "$ARCHITECTURE" = "x86_64" ]; then \
        export CHROME_ARCH="amd64"; \
    elif [ "$ARCHITECTURE" = "aarch64" ]; then \
        export CHROME_ARCH="arm64"; \
    else \
        echo "Unsupported architecture: $ARCHITECTURE"; \
        exit 1; \
    fi; \
    echo "Architecture: $CHROME_ARCH"

RUN apt-get update \
    && apt-get install -y wget gnupg\
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=$CHROME_ARCH] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list' \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL = INFO

CMD ["python", "main.py"]