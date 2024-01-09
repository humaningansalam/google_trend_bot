FROM python:3.10.13-slim

WORKDIR /usr/src/app

COPY . .

RUN apt-get update \
    && apt-get install -y google-chrome-stable \
    && python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

WORKDIR ./myapp

ENV SLACK_WEBHOOK=api_key

CMD ["python", "main.py"]