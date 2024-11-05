FROM python:3.10-slim-bookworm

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    wget \
    unzip \ 
    curl \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcb1 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && python -m pip install --upgrade pip\
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root \
    && poetry run playwright install chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

EXPOSE 5000

CMD ["python3", "-m", "myapp.src.main"]
