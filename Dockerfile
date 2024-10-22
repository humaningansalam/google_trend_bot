FROM python:3.10-slim-bookworm

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget unzip curl chromium chromium-driver \
    && python -m pip install --upgrade pip\
    && pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false \
    && poetry install --no-root \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

EXPOSE 5000

CMD ["python3", "-m", "myapp.src.main"]
