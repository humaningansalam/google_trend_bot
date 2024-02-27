FROM ubuntu:22.04

WORKDIR /usr/src/app

COPY . .

RUN apt-get update
RUN apt-get install -y --no-install-recommends python3 python3-pip wget unzip curl libglib2.0-0 libnss3 libfontconfig1 libxrender1 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango1.0-0 libasound2
RUN chmod +x ./script/install.sh  && ./script/install.sh
RUN pip3 install --upgrade pip
RUN pip3 install --no-cache-dir -r requirements.txt
RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

CMD ["python3", "main.py"]
