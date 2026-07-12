from __future__ import annotations

from src.scoring import score_market, status_for


BASE_METRICS = {
    "below_50_fraction": 0.0,
    "below_200_fraction": 0.0,
    "basket_drawdown": 0.0,
    "volatility_percentile": 0.5,
    "relative_63d_vs_spy": 0.0,
}


def test_score_market_has_no_points_when_thresholds_do_not_trigger() -> None:
    score, evidence = score_market(BASE_METRICS)

    assert score == 0
    assert evidence == []


def test_score_market_accumulates_triggered_evidence() -> None:
    metrics = BASE_METRICS | {
        "below_50_fraction": 0.8,
        "below_200_fraction": 0.6,
        "basket_drawdown": -0.25,
        "volatility_percentile": 0.95,
        "relative_63d_vs_spy": -0.12,
    }

    score, evidence = score_market(metrics)

    assert score == 94
    assert [item["signal"] for item in evidence] == [
        "Market breadth",
        "Long-term trend",
        "Drawdown",
        "Volatility",
        "Relative weakness",
    ]


def test_status_for_uses_default_thresholds() -> None:
    assert status_for(0) == "Normal"
    assert status_for(30) == "Elevated"
    assert status_for(45) == "Strained"
    assert status_for(60) == "High risk"
    assert status_for(80) == "Severe"


def test_status_for_accepts_configured_thresholds() -> None:
    thresholds = {
        "normal": 10,
        "elevated": 20,
        "strained": 30,
        "high_risk": 40,
    }

    assert status_for(35, thresholds) == "High risk"
    assert status_for(45, thresholds) == "Severe"
