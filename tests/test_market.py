from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.market import MarketDataError, _download_tiingo_ticker, calculate_market_metrics, download_prices


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.requests = []

    def get(self, *args, **kwargs) -> FakeResponse:
        self.requests.append((args, kwargs))
        return FakeResponse(self.payload)


def fixture_prices() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=260)
    return pd.DataFrame(
        {
            "AAA": np.linspace(200, 100, len(dates)),
            "BBB": np.linspace(100, 200, len(dates)),
            "SPY": np.linspace(100, 150, len(dates)),
        },
        index=dates,
    )


def test_calculate_market_metrics_returns_transparent_snapshot() -> None:
    prices = fixture_prices()

    metrics = calculate_market_metrics(prices, ["AAA", "BBB"], "SPY")

    assert metrics["source"] == "Tiingo"
    assert metrics["as_of"] == prices.index[-1].date().isoformat()
    assert metrics["below_50_fraction"] == 0.5
    assert metrics["below_200_fraction"] == 0.5
    assert len(metrics["basket_history"]) == 180

    by_ticker = {row["ticker"]: row for row in metrics["tickers"]}
    assert by_ticker["AAA"]["below_50dma"] is True
    assert by_ticker["BBB"]["below_50dma"] is False
    assert by_ticker["BBB"]["drawdown_52w"] == 0.0


def test_calculate_market_metrics_requires_basket_coverage() -> None:
    with pytest.raises(MarketDataError, match="None of the configured AI-basket"):
        calculate_market_metrics(fixture_prices(), ["MISSING"], "SPY")


def test_download_tiingo_ticker_parses_adjusted_closes() -> None:
    session = FakeSession(
        [
            {"date": "2026-01-02T00:00:00.000Z", "adjClose": 101.25},
            {"date": "2026-01-03T00:00:00.000Z", "adjClose": 102.5},
        ]
    )

    series = _download_tiingo_ticker("AAA", session, "2026-01-01")

    assert series.name == "AAA"
    assert series.iloc[-1] == 102.5
    request_args, request_kwargs = session.requests[0]
    assert request_args[0].endswith("/AAA/prices")
    assert request_kwargs["params"] == {"startDate": "2026-01-01", "format": "json"}


def test_download_tiingo_ticker_reports_api_error_payload() -> None:
    with pytest.raises(MarketDataError, match="Invalid token"):
        _download_tiingo_ticker("AAA", FakeSession({"detail": "Invalid token"}), "2026-01-01")


def test_download_prices_requires_tiingo_token(monkeypatch) -> None:
    monkeypatch.delenv("TIINGO_API_TOKEN", raising=False)

    with pytest.raises(MarketDataError, match="TIINGO_API_TOKEN"):
        download_prices(["AAA"])
