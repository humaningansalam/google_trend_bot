# Google Trend Bot

A small Flask service that sends new Google Trends RSS entries to Slack and exposes an on-demand Google Trends scraper.

## Runtime flow

- `TrendAlertBot` polls the Korea Google Trends RSS feed on one in-process scheduler thread.
- A title is sent once, then remembered for three days. Failed Slack deliveries remain eligible for retry.
- `GET /trends` runs the Playwright crawler locally or submits the same crawler to a remote Playwright job server.
- Flask exposes health, control, scrape, and Prometheus endpoints. Gunicorn runs one process so the scheduler is not duplicated.

## Local setup

```bash
cp .env.example .env
# Set SLACK_WEBHOOK in .env before starting the service.

uv sync --group dev
uv run playwright install chromium
uv run --env-file .env python -m src.main
```

On Linux machines without Chromium system libraries, install them with:

```bash
uv run playwright install --with-deps chromium
```

The development server binds to `127.0.0.1:5000` by default. `uv run` does not load `.env` unless `--env-file` is supplied.

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SLACK_WEBHOOK` | yes | none | Slack incoming webhook used for trend alerts. Startup fails when it is empty. |
| `SCHEDULE_INTERVAL` | no | `10` | RSS poll interval in minutes; must be a positive integer. |
| `SCRAPER_BACKEND` | no | `local` | `local` runs Chromium in this service; `remote` uses the Playwright job API. |
| `PLAYWRIGHT_URL` | remote only | `http://localhost:3000` | Absolute base URL for the remote Playwright job API. |
| `CONTROL_TOKEN` | no | none | Bearer token for `/start`, `/stop`, and `/trends/prune`. Without it, protect those routes at the network layer. |
| `LOKI_URL` | no | none | Loki push endpoint. Empty disables Loki output. |
| `LOG_LEVEL` | no | `INFO` | Python log level. |
| `LOG_FILE` | no | `./logs/bot.log` | Local log file path. |
| `APP_NAME` | no | `google-trend-bot` | Application label used in logs. |
| `APP_ENV` | no | `dev` | Environment label used in logs. |
| `BIND_HOST` | no | `127.0.0.1` | Host used by the development server. |
| `PORT` | no | `5000` | TCP port used by the development server; must be between 1 and 65535. |
| `VERSION` | Compose only | `dev` when unset | Container image tag; set it to the project release version. |

## Verification

Run the same checks enforced by CI:

```bash
uv sync --frozen --group dev
uv run ruff check .
uv run ruff format --check .
uv run pip-audit --local --progress-spinner off
uv run pytest -q
uv run python -m compileall -q src tests
```

`pip-audit` reports the Git-pinned `his-monitoring` package as unauditable because it is not published on PyPI. Its source revision is pinned in `pyproject.toml`; all registry packages must report zero known vulnerabilities.

To apply the formatter locally:

```bash
uv run ruff format .
```

## HTTP API

| Method | Path | Behavior |
| --- | --- | --- |
| `GET` | `/health` | Returns `Healthy`; `X-Bot-Active` reports the scheduler thread state. |
| `POST` | `/start` | Starts the scheduler or returns `bot_already_running`. |
| `POST` | `/stop` | Returns `stopped` or `stopping` when the bounded join times out. |
| `POST` | `/trends/prune` | Prunes titles older than the three-day memory window. |
| `GET` | `/trends` | Returns data from the selected scraper. Upstream failures include an error code. |
| `GET` | `/metrics` | Exposes Prometheus metrics. |

When `CONTROL_TOKEN` is set, send `Authorization: Bearer <token>` to the three state-changing endpoints. Read-only endpoints remain open. Clients should branch on JSON `code`, not the human-readable `message`.

### Prometheus metrics

| Metric | Measures |
| --- | --- |
| `trends_bot_rss_poll_duration_seconds` | Time spent polling and processing the RSS feed. |
| `trends_bot_completed_rss_polls_total` | RSS polls completed without a delivery failure. |
| `trends_bot_delivered_alerts_total` | Trend alerts delivered to Slack. |

Error labels distinguish `rss_poll_error` from `alert_delivery_error`.

## Docker Compose

```bash
cp .env.example .env
# Set SLACK_WEBHOOK in .env.
export VERSION=0.5.0

docker network inspect bridge_server >/dev/null 2>&1 \
  || docker network create bridge_server
docker compose up --build -d
docker compose ps
docker compose down
```

Compose publishes the service at `http://localhost:12025`, adds a container health check, and uses an external `bridge_server` network. The image runs as a non-root user. Local scraping needs the Chromium dependencies installed in the image; remote scraping does not invoke the bundled browser.

## Source map

```text
src/bot/trend_alert_bot.py       RSS scheduling, deduplication, Slack delivery
src/bot/scraper.py               local/remote scraper selection
src/clients/playwright_submit.py remote job protocol client
src/common/                      API, RSS, scrape, and metrics contracts
src/crawl_scripts/               Playwright crawler submitted locally or remotely
src/main.py                      Flask routes and runtime assembly
```
