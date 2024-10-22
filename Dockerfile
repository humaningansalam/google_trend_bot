FROM debian:bullseye-slim

# 가상환경을 사용하도록 설정
ENV POETRY_VIRTUALENVS_CREATE=true
ENV POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
&& apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl chromium chromium-driver \
&& pip install --no-cache-dir poetry \
&& poetry install --no-root \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

EXPOSE 5000

CMD ["python3", "-m", "myapp.src.main"]
