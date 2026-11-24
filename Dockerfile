FROM python:3.11-slim-bookworm AS dependencies

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.9.16 /uv /bin/uv

WORKDIR /usr/src/app

COPY .python-version pyproject.toml uv.lock ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && uv sync \
        --python /usr/local/bin/python3.11 \
        --frozen \
        --no-dev \
        --no-install-project \
    && rm -rf /root/.cache/uv /var/lib/apt/lists/*


FROM python:3.11-slim-bookworm AS runtime

ARG VERSION=dev

ENV VERSION=${VERSION} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH="/usr/src/app/.venv/bin:${PATH}" \
    LOG_LEVEL=INFO \
    LOG_FILE=./logs/bot.log \
    SCHEDULE_INTERVAL=10

WORKDIR /usr/src/app

COPY --from=dependencies /usr/src/app/.venv ./.venv
RUN DEBIAN_FRONTEND=noninteractive \
    playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/* \
    && chmod -R a+rX /ms-playwright \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin app \
    && mkdir -p logs \
    && chown app:app logs

COPY . .

ENV HOME=/home/app

USER app

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "src.main:create_runtime_app()"]
