from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
CONFIG_PATH = ROOT / "config" / "signals.json"

REQUIRED_CONFIG_KEYS = {
    "tickers",
    "ai_basket",
    "benchmark",
    "market_data_provider",
    "weights",
    "alert_threshold_change",
    "status_thresholds",
}

STATUS_THRESHOLD_KEYS = ("normal", "elevated", "strained", "high_risk")


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_CONFIG_KEYS - set(config))
    if missing:
        raise ValueError(f"Missing required config key(s): {', '.join(missing)}")

    tickers = config["tickers"]
    ai_basket = config["ai_basket"]
    benchmark = config["benchmark"]
    provider = config["market_data_provider"]

    if not isinstance(tickers, list) or not tickers:
        raise ValueError("Config key 'tickers' must be a non-empty list.")

    if not isinstance(ai_basket, list) or not ai_basket:
        raise ValueError("Config key 'ai_basket' must be a non-empty list.")

    if not all(isinstance(ticker, str) and ticker for ticker in tickers):
        raise ValueError("Config key 'tickers' must contain only non-empty strings.")

    if not all(isinstance(ticker, str) and ticker for ticker in ai_basket):
        raise ValueError("Config key 'ai_basket' must contain only non-empty strings.")

    if not isinstance(benchmark, str) or not benchmark:
        raise ValueError("Config key 'benchmark' must be a non-empty string.")

    if provider != "tiingo":
        raise ValueError("Config key 'market_data_provider' must be 'tiingo'.")

    configured_tickers = set(tickers)
    missing_market_tickers = sorted((set(ai_basket) | {benchmark}) - configured_tickers)
    if missing_market_tickers:
        raise ValueError(
            "Every ai_basket ticker and benchmark must also appear in tickers: "
            + ", ".join(missing_market_tickers)
        )

    status_thresholds = config["status_thresholds"]
    if not isinstance(status_thresholds, dict):
        raise ValueError("Config key 'status_thresholds' must be an object.")

    missing_thresholds = [
        key for key in STATUS_THRESHOLD_KEYS
        if key not in status_thresholds
    ]
    if missing_thresholds:
        raise ValueError(
            "Missing status threshold(s): " + ", ".join(missing_thresholds)
        )

    ordered_thresholds = [status_thresholds[key] for key in STATUS_THRESHOLD_KEYS]
    if ordered_thresholds != sorted(ordered_thresholds):
        raise ValueError("Status thresholds must increase from normal to high_risk.")

    if not all(isinstance(value, (int, float)) and 0 <= value <= 100 for value in ordered_thresholds):
        raise ValueError("Status thresholds must be numeric values between 0 and 100.")

    alert_threshold = config["alert_threshold_change"]
    if not isinstance(alert_threshold, (int, float)) or alert_threshold < 0:
        raise ValueError("Config key 'alert_threshold_change' must be a non-negative number.")

    return config


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return validate_config(json.load(handle))
