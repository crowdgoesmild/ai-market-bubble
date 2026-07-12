from __future__ import annotations

import pytest

from src.config import validate_config


def valid_config() -> dict:
    return {
        "tickers": ["AAA", "BBB", "SPY"],
        "ai_basket": ["AAA", "BBB"],
        "benchmark": "SPY",
        "market_data_provider": "tiingo",
        "weights": {
            "market": 0.35,
            "fundamentals": 0.25,
            "capex_narrative": 0.15,
            "adoption": 0.1,
            "macro": 0.1,
            "private_market": 0.05,
        },
        "alert_threshold_change": 5,
        "status_thresholds": {
            "normal": 25,
            "elevated": 40,
            "strained": 55,
            "high_risk": 70,
        },
    }


def test_validate_config_accepts_project_shape() -> None:
    config = valid_config()

    assert validate_config(config) is config


def test_validate_config_rejects_missing_required_keys() -> None:
    config = valid_config()
    del config["benchmark"]

    with pytest.raises(ValueError, match="Missing required config"):
        validate_config(config)


def test_validate_config_requires_basket_and_benchmark_in_tickers() -> None:
    config = valid_config()
    config["ai_basket"].append("MISSING")

    with pytest.raises(ValueError, match="Every ai_basket ticker"):
        validate_config(config)


def test_validate_config_requires_ordered_status_thresholds() -> None:
    config = valid_config()
    config["status_thresholds"]["elevated"] = 20

    with pytest.raises(ValueError, match="increase"):
        validate_config(config)


def test_validate_config_requires_tiingo_provider() -> None:
    config = valid_config()
    config["market_data_provider"] = "stooq"

    with pytest.raises(ValueError, match="market_data_provider"):
        validate_config(config)
