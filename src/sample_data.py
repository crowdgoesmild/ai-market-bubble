from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .market import calculate_market_metrics
from .scoring import score_market, status_for


def build_sample_prices(
    tickers: list[str],
    ai_basket: list[str],
    benchmark: str,
    periods: int = 260,
) -> pd.DataFrame:
    dates = pd.bdate_range(end=pd.Timestamp("2026-01-02"), periods=periods)
    x_axis = np.linspace(0, 1, periods)
    data: dict[str, np.ndarray] = {}

    for index, ticker in enumerate(tickers):
        trend = 1 + (0.22 - index * 0.01) * x_axis
        cycle = 1 + 0.035 * np.sin(np.linspace(0, 8, periods) + index / 2)
        series = 100 * trend * cycle

        if ticker in ai_basket and index % 2 == 0:
            series[-70:] *= np.linspace(1, 0.82, 70)
        elif ticker in ai_basket:
            series[-45:] *= np.linspace(1, 0.93, 45)

        if ticker == benchmark:
            series = 100 * (1 + 0.16 * x_axis) * (1 + 0.015 * np.sin(np.linspace(0, 7, periods)))

        data[ticker] = np.maximum(series, 1.0)

    return pd.DataFrame(data, index=dates)


def build_sample_payload(config: dict) -> tuple[dict, list[dict]]:
    prices = build_sample_prices(
        config["tickers"],
        config["ai_basket"],
        config["benchmark"],
    )
    market = calculate_market_metrics(
        prices,
        config["ai_basket"],
        config["benchmark"],
    )
    market["source"] = "Synthetic sample"

    score, evidence = score_market(market)
    thresholds = config.get("status_thresholds")
    history_seed = market["basket_history"][-90:]

    history = []
    for index, row in enumerate(history_seed):
        drift = (index - len(history_seed) + 1) * 0.12
        wave = 4 * np.sin(index / 7)
        history_score = round(max(0, min(100, score + drift + wave)), 1)
        history.append(
            {
                "date": row["date"],
                "score": history_score,
                "status": status_for(history_score, thresholds),
            }
        )

    latest = {
        "as_of": market["as_of"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "status": status_for(score, thresholds),
        "confidence": 0.55,
        "category_scores": {
            "market": score,
            "fundamentals": None,
            "capex_narrative": None,
            "adoption": None,
            "macro": None,
            "private_market": None,
        },
        "market": market,
        "evidence": evidence,
    }

    return latest, history
