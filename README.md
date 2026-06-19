# google_trend_bot

Google Trends alerts for Slack with a small Flask control surface.

## Local run

1. Copy `.env.example` to `.env` and fill in the required values.
2. Install dependencies with `uv sync`.
3. Start the service with `uv run python -m src.main`.

## Environment variables

- `SLACK_WEBHOOK`: Slack incoming webhook URL.
- `LOKI_URL`: Loki push endpoint used by logging.
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

- `Dockerfile` sets the same runtime defaults as `.env.example`, including `LOKI_URL` and `SCHEDULE_INTERVAL`.
- `docker-compose.yml` expects an `.env` file beside it and publishes the app on port `12025`.
- The container listens on port `5000` internally.

## Endpoints

- `GET /health` returns `Healthy`.
- `POST /start` starts the RSS bot.
- `POST /stop` stops the RSS bot.
- `POST /reset` clears old trend memory.
- `GET /trends` returns `{"status":"success","data":...}` on success or `{"status":"error","message":...}` on failure.
- `GET /metrics` exposes Prometheus metrics.
