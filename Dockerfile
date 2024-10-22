FROM debian:bullseye-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
&& apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl chromium chromium-driver \
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
