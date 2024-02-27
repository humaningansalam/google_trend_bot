FROM debian:bullseye-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
&& apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl chromium \
&& pip3 install --upgrade pip \
&& pip3 install --no-cache-dir -r requirements.txt \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

CMD ["python3", "main.py"]
