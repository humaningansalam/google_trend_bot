FROM debian:bookworm-slim

ARG VERSION
ARG INSTALL_DEV=false

ENV VERSION=$VERSION
ENV SLACK_WEBHOOK=api_key
ENV FLUENTD_URL=fluentd_url
ENV LOG_LEVEL=INFO

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /usr/src/app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    git \
    wget \
    unzip \ 
    curl \
    ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libatspi2.0-0 libxcb1 libx11-6 libxcomposite1 \
    libxdamage1 libxext6 libxfixes3 libxrandr2 \
    libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --python 3.11 --no-install-project && \
    if [ "$INSTALL_DEV" = "true" ]; then \
        uv sync --frozen --python 3.11 --group dev --no-install-project; \
    fi

# Playwright용 Chromium 브라우저 설치 (의존성 포함)
RUN uv run playwright install --with-deps chromium

COPY . .

ENV PATH="/usr/src/app/.venv/bin:$PATH"

EXPOSE 5000

CMD ["python", "-m", "src.main"]
