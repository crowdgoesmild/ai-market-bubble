# AI Bubble Monitor Agent Notes

This project is a small Python data pipeline that produces a static AI-market stress dashboard.

## Useful Commands

- `make setup` installs runtime and dev dependencies into `.venv`.
- `make run` runs the daily monitor and writes `data/latest.json`, `data/score_history.json`, `docs/data.json`, and `docs/index.html`.
- `make sample` writes a synthetic preview dashboard to `docs/sample.html`.
- `make test` runs the local test suite.
- `make lint` runs Ruff checks.

## Project Shape

- `src/market.py` owns external market-data download and market metric calculation.
- `src/scoring.py` converts market metrics into transparent score evidence.
- `src/dashboard.py` renders the static HTML dashboard.
- `src/sample_data.py` builds deterministic offline fixtures for UI work.
- `src/run_daily.py` orchestrates config, persistence, dashboard output, and notifications.
- `config/signals.json` is the main product configuration.
- Live market data uses Tiingo EOD and requires `TIINGO_API_TOKEN`.

## Working Rules

- Keep generated dashboard and data files out of hand edits; regenerate them with `python -m src.run_daily`.
- Keep network access isolated behind source modules that can be tested with local fixtures.
- Add or update tests when changing signal math, score thresholds, output contracts, or notification behavior.
- Preserve the current scope: version 0.2 is market-stress only; fundamentals, macro, adoption, private-market, and filing-language signals are placeholders for later iterations.
