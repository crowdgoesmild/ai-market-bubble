from __future__ import annotations

import os
import time

import pandas as pd
import requests


TIINGO_EOD_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices"
SUPPORTED_MARKET_DATA_PROVIDERS = {"tiingo"}


class MarketDataError(RuntimeError):
    """Raised when market data cannot be obtained or validated."""


def _start_date_for_period(period: str) -> str:
    offsets = {
        "1y": pd.DateOffset(years=1, months=2),
        "2y": pd.DateOffset(years=2, months=2),
        "5y": pd.DateOffset(years=5, months=2),
    }

    if period not in offsets:
        raise ValueError(
            f"Unsupported period {period!r}. Supported periods are: "
            + ", ".join(sorted(offsets))
        )

    start_date = pd.Timestamp.now().normalize() - offsets[period]
    return start_date.date().isoformat()


def _download_tiingo_ticker(
    ticker: str,
    session: requests.Session,
    start_date: str,
    timeout: int = 30,
) -> pd.Series:
    response = session.get(
        TIINGO_EOD_URL.format(ticker=ticker.upper()),
        params={"startDate": start_date, "format": "json"},
        timeout=timeout,
    )
    response.raise_for_status()

    try:
        payload = response.json()
    except ValueError as exc:
        raise MarketDataError(f"Tiingo returned non-JSON data for {ticker}.") from exc

    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message") or payload
        raise MarketDataError(f"Tiingo returned an error for {ticker}: {detail}")

    if not isinstance(payload, list):
        raise MarketDataError(f"Unexpected Tiingo response for {ticker}: {type(payload).__name__}")

    if not payload:
        raise MarketDataError(f"Tiingo returned no data for {ticker}.")

    frame = pd.DataFrame(payload)
    required_columns = {"date", "adjClose"}
    if not required_columns.issubset(frame.columns):
        raise MarketDataError(f"Unexpected Tiingo response for {ticker}: columns were {list(frame.columns)}")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.tz_convert(None)
    frame["adjClose"] = pd.to_numeric(frame["adjClose"], errors="coerce")
    frame = frame.dropna(subset=["date", "adjClose"]).drop_duplicates(subset=["date"], keep="last").sort_values("date")

    if frame.empty:
        raise MarketDataError(f"No valid closing prices were found for {ticker}.")

    series = frame.set_index("date")["adjClose"]
    series.name = ticker
    return series


def download_prices(
    tickers: list[str],
    period: str = "2y",
    provider: str = "tiingo",
    token: str | None = None,
) -> pd.DataFrame:
    if not tickers:
        raise ValueError("At least one ticker must be supplied.")

    if provider not in SUPPORTED_MARKET_DATA_PROVIDERS:
        raise ValueError(
            f"Unsupported market data provider {provider!r}. "
            f"Supported providers are: {', '.join(sorted(SUPPORTED_MARKET_DATA_PROVIDERS))}"
        )

    token = token or os.getenv("TIINGO_API_TOKEN")
    if not token:
        raise MarketDataError(
            "TIINGO_API_TOKEN is required to download live market data. "
            "Set it locally or add it as a GitHub Actions secret."
        )

    start_date = _start_date_for_period(period)

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Token {token}",
            "Content-Type": "application/json",
            "User-Agent": (
                "ai-bubble-monitor/0.2 "
                "(https://github.com/)"
            )
        }
    )

    series_by_ticker: list[pd.Series] = []
    errors: list[str] = []

    for ticker in tickers:
        try:
            series_by_ticker.append(_download_tiingo_ticker(ticker, session, start_date))
        except (requests.RequestException, MarketDataError, ValueError) as exc:
            errors.append(f"{ticker}: {exc}")

        time.sleep(0.2)

    if not series_by_ticker:
        detail = "; ".join(errors)
        raise MarketDataError(f"All market-data downloads failed. {detail}")

    prices = pd.concat(series_by_ticker, axis=1)
    prices = prices.dropna(how="all").sort_index()

    cutoff = pd.Timestamp(start_date)
    prices = prices.loc[prices.index >= cutoff]

    successful = set(prices.columns)
    missing = [ticker for ticker in tickers if ticker not in successful]

    if missing:
        print("Warning: no market data was available for: " + ", ".join(missing))

    if len(prices) < 200:
        raise MarketDataError(
            f"Only {len(prices)} trading days were returned; at least 200 are required."
        )

    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    return prices


def calculate_market_metrics(
    prices: pd.DataFrame,
    basket: list[str],
    benchmark: str,
    source: str = "Tiingo",
) -> dict:
    available = [ticker for ticker in basket if ticker in prices.columns]

    if not available:
        raise MarketDataError(
            "None of the configured AI-basket tickers were returned."
        )

    latest = prices.iloc[-1]
    ma50 = prices.rolling(50, min_periods=50).mean().iloc[-1]
    ma200 = prices.rolling(200, min_periods=200).mean().iloc[-1]
    high_252 = prices.rolling(252, min_periods=100).max().iloc[-1]

    valid_50 = [
        ticker for ticker in available
        if pd.notna(latest[ticker]) and pd.notna(ma50[ticker])
    ]
    valid_200 = [
        ticker for ticker in available
        if pd.notna(latest[ticker]) and pd.notna(ma200[ticker])
    ]

    if not valid_50 or not valid_200:
        raise MarketDataError(
            "Insufficient data to calculate moving-average breadth."
        )

    below_50 = float((latest[valid_50] < ma50[valid_50]).mean())
    below_200 = float((latest[valid_200] < ma200[valid_200]).mean())

    basket_returns = prices[available].pct_change(fill_method=None)
    basket_series = basket_returns.mean(axis=1, skipna=True)
    basket_index = (1 + basket_series.fillna(0)).cumprod()

    drawdown = float(
        basket_index.iloc[-1] / basket_index.cummax().iloc[-1] - 1
    )

    rolling_vol = basket_series.rolling(20).std() * (252 ** 0.5)
    valid_volatility = rolling_vol.dropna()

    if valid_volatility.empty:
        raise MarketDataError(
            "Insufficient data to calculate volatility."
        )

    current_vol = float(valid_volatility.iloc[-1])
    vol_percentile = float((valid_volatility <= current_vol).mean())

    relative_63d = 0.0
    if benchmark in prices.columns and len(prices) >= 64:
        benchmark_prices = prices[benchmark].dropna()

        if len(benchmark_prices) >= 64:
            basket_return = float(
                basket_index.iloc[-1] / basket_index.iloc[-64] - 1
            )
            benchmark_return = float(
                benchmark_prices.iloc[-1] / benchmark_prices.iloc[-64] - 1
            )
            relative_63d = basket_return - benchmark_return

    ticker_rows = []
    for ticker in available:
        if pd.isna(latest[ticker]):
            continue

        ticker_drawdown = None
        if pd.notna(high_252[ticker]):
            ticker_drawdown = round(
                float(latest[ticker] / high_252[ticker] - 1),
                4,
            )

        ticker_rows.append(
            {
                "ticker": ticker,
                "price": round(float(latest[ticker]), 2),
                "below_50dma": (
                    bool(latest[ticker] < ma50[ticker])
                    if pd.notna(ma50[ticker])
                    else None
                ),
                "below_200dma": (
                    bool(latest[ticker] < ma200[ticker])
                    if pd.notna(ma200[ticker])
                    else None
                ),
                "drawdown_52w": ticker_drawdown,
            }
        )

    return {
        "source": source,
        "as_of": prices.index[-1].date().isoformat(),
        "below_50_fraction": round(below_50, 4),
        "below_200_fraction": round(below_200, 4),
        "basket_drawdown": round(drawdown, 4),
        "annualised_volatility": round(current_vol, 4),
        "volatility_percentile": round(vol_percentile, 4),
        "relative_63d_vs_spy": round(relative_63d, 4),
        "tickers": ticker_rows,
        "basket_history": [
            {
                "date": index.date().isoformat(),
                "value": round(float(value), 5),
            }
            for index, value in basket_index.tail(180).items()
        ],
    }
