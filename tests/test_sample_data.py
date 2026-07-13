from __future__ import annotations

from src.sample_data import build_sample_payload


def sample_config() -> dict:
    return {
        "tickers": ["AAA", "BBB", "CCC", "SPY"],
        "ai_basket": ["AAA", "BBB", "CCC"],
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
        "status_thresholds": {
            "normal": 25,
            "elevated": 40,
            "strained": 55,
            "high_risk": 70,
        },
    }


def test_build_sample_payload_matches_dashboard_contract() -> None:
    latest, history = build_sample_payload(sample_config())

    assert latest["market"]["source"] == "Synthetic sample"
    assert 0 <= latest["score"] <= 100
    assert latest["status"]
    assert latest["categories"]["market"]["active"] is True
    assert len(history) == 90
    assert latest["market"]["basket_history"]
