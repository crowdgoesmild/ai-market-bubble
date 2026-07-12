# AI Bubble Monitor

A small, free daily monitoring pipeline that tracks stress in AI-linked public markets.

The current implementation:

- downloads daily market data from Tiingo EOD;
- calculates breadth, drawdown, relative strength, and volatility signals;
- produces a transparent 0-100 stress score with evidence rows;
- writes JSON snapshots to `data/` and `docs/data.json`;
- renders a static dashboard to `docs/index.html`;
- optionally sends Discord alerts;
- runs automatically with GitHub Actions.

The score is an indicator of market stress, not a crash prediction.

## Quick Start

Requires Python 3.11-3.13. CI uses Python 3.12.

Use the project Makefile:

```bash
make setup
make test
make sample
open docs/sample.html
```

When live market data is reachable:

```bash
export TIINGO_API_TOKEN="..."
make run
open docs/index.html
```

Or run the same steps manually:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
python -m src.run_sample
open docs/sample.html
```

On Windows, activate the virtual environment with:

```powershell
.venv\Scripts\activate
```

## Development Commands

- `make setup` creates `.venv` and installs runtime plus test/lint dependencies.
- `PYTHON=python3.11 make setup` or `PYTHON=python3.13 make setup` uses another supported interpreter.
- `make run` runs the daily monitor.
- `make sample` writes a synthetic dashboard preview to `docs/sample.html`.
- `make test` runs the unit tests.
- `make lint` runs Ruff checks.
- `python -m src.run_daily` is the direct pipeline entry point.

## Configuration

Edit `config/signals.json` to change the monitored universe:

- `tickers`: all symbols to download from Tiingo EOD.
- `market_data_provider`: the live market-data provider, currently `tiingo`.
- `ai_basket`: the equal-weight AI basket used for stress signals.
- `benchmark`: the relative-strength benchmark, currently `SPY`.
- `status_thresholds`: score boundaries for Normal, Elevated, Strained, High risk, and Severe.
- `alert_threshold_change`: score movement required before Discord sends another same-status alert.

The pipeline validates this config at startup so missing basket members or invalid thresholds fail early.

## Outputs

Running the monitor writes:

- `data/latest.json`: full latest run payload.
- `data/score_history.json`: historical score series.
- `docs/data.json`: latest payload for static hosting.
- `docs/index.html`: static Plotly dashboard.

Treat these as generated outputs. Rebuild them with `python -m src.run_daily`.

For dashboard or UI work without live market-data access, run:

```bash
python -m src.run_sample
open docs/sample.html
```

This writes `docs/sample.html` and `docs/sample-data.json` from deterministic synthetic prices.

## Discord Alerts

Create a Discord webhook and set it locally:

```bash
export TIINGO_API_TOKEN="..."
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
export DASHBOARD_URL="https://<your-github-user>.github.io/ai-bubble-monitor/"
```

For local development, copy `.env.example` into your shell or a local environment manager.

In GitHub, add:

- an Actions secret named `TIINGO_API_TOKEN`;
- an Actions secret named `DISCORD_WEBHOOK_URL`;
- an optional repository variable named `DASHBOARD_URL`.

## Automation

Two workflows are scaffolded:

- `.github/workflows/ci.yml` runs tests on push and pull request.
- `.github/workflows/daily-monitor.yml` runs the monitor on weekdays and commits updated `data/` and `docs/` outputs.

GitHub Actions cron schedules are UTC. Adjust the cron if you want a different market-close cadence.

## Project Map

- `src/config.py`: paths and config validation.
- `src/market.py`: Tiingo EOD download and market metric calculation.
- `src/scoring.py`: score and status logic.
- `src/dashboard.py`: static HTML dashboard rendering.
- `src/sample_data.py`: deterministic synthetic data for offline dashboard work.
- `src/run_sample.py`: offline sample dashboard entry point.
- `src/discord_notify.py`: optional Discord notification.
- `src/run_daily.py`: daily orchestration entry point.
- `tests/`: focused tests for config, scoring, market metrics, dashboard output, and alerts.
- `AGENTS.md`: working notes for future Codex sessions.

## Current Scope

Version 0.2 implements the daily market-stress layer using Tiingo EOD instead of browser-gated public endpoints.

SEC fundamentals, FRED macro data, adoption metrics, private-market data, and filing-language analysis are represented in the data model but intentionally left for later iterations.

## Troubleshooting

If `TIINGO_API_TOKEN` is missing or invalid, the live run will stop with a clear `MarketDataError`. Use `make sample` for local UI work without a live token.

Tiingo's EOD documentation lists the historical prices endpoint as `/tiingo/daily/<ticker>/prices` with `startDate` support, and includes adjusted close as `adjClose`: https://www.tiingo.com/documentation/end-of-day
