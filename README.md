# google_trend_bot

Google Trends alerts for Slack with a small Flask control surface.

## Local run

1. Copy `.env.example` to `.env` and fill in `SLACK_WEBHOOK`.
2. Install dependencies with `uv sync`.
3. Install the Chromium browser used by the local scraper with `uv run playwright install chromium`.
4. Start the service with `uv run --env-file .env python -m src.main`.

`uv run` does not load `.env` automatically, so keep the `--env-file .env` option when starting the service locally.
Leave `LOKI_URL` empty unless a Loki push endpoint is reachable from the local machine.

On Linux hosts that do not already have Chromium system libraries, run `uv run playwright install --with-deps chromium` instead.

## Environment variables

- `SLACK_WEBHOOK`: Slack incoming webhook URL.
- `VERSION`: Container image tag used by Compose, default `0.3.3` in `.env.example`.
- `LOKI_URL`: Optional Loki push endpoint used by logging. Leave it empty to disable Loki output.
- `SCHEDULE_INTERVAL`: RSS polling interval in minutes. Must be a positive integer.
- `CONTROL_TOKEN`: Optional bearer token for `/start`, `/stop`, and `/reset`. When unset, those endpoints keep their current local behavior.
- `LOG_LEVEL`: Python log level, default `INFO`.
- `APP_NAME`: App tag written into logs, default `google-trend-bot`.
- `APP_ENV`: Environment tag written into logs, default `dev`.
- `USE_SERVER`: Set to `True` to run scraper jobs through the server submit path.
- `PLAYWRIGHT_URL`: Browser automation base URL used by scraping support code.

## Tests

- Run the focused suite with `uv run pytest -q tests/test_bot.py tests/test_scraper.py tests/test_flask_app.py tests/test_config.py`.
- Run the full suite with `uv run pytest -q`.
- Run a syntax check with `uv run python -m py_compile src/config.py src/main.py src/bot/rss_bot.py src/bot/scraper.py`.

## Docker and Compose

1. Copy `.env.example` to `.env` and fill in `SLACK_WEBHOOK`.
2. Create the external network expected by Compose if it does not already exist:
   `docker network inspect bridge_server >/dev/null 2>&1 || docker network create bridge_server`.
3. If Loki is attached to that network, set `LOKI_URL` to its push endpoint. Otherwise leave it empty.
4. Build and start the service with `docker compose up --build -d`.
5. Verify it with `curl --fail http://localhost:12025/health`.
6. Stop it with `docker compose down`.

- `Dockerfile` provides container fallback values for `LOG_LEVEL` and `SCHEDULE_INTERVAL`; `.env` remains the Compose runtime source of truth.
- `docker-compose.yml` expects an `.env` file beside it, including `VERSION`, and publishes the app on port `12025`.
- The container listens on port `5000` internally.
- The container runs Gunicorn with one worker to keep the scheduler single-instance and four request threads so scraper calls do not block health and control requests.

## Endpoints

- `GET /health` returns `Healthy`.
- `POST /start` starts the RSS bot.
- `POST /stop` stops the RSS bot.
- `POST /reset` clears old trend memory.
- `GET /trends` returns `{"status":"success","data":...}` on success or `{"status":"error","message":...}` on failure.
- `GET /metrics` exposes Prometheus metrics.
