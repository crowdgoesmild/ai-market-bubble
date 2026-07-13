from __future__ import annotations

from datetime import date
import os

import pandas as pd
import requests

from .category_scoring import active_category, inactive_category

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


class MacroDataError(RuntimeError):
    """Raised when macro data cannot be obtained or validated."""


def _start_date(years: int = 3) -> str:
    return (pd.Timestamp(date.today()) - pd.DateOffset(years=years)).date().isoformat()


def _series_from_observations(payload: dict, label: str) -> pd.Series:
    observations = payload.get("observations")
    if not isinstance(observations, list):
        raise MacroDataError(f"FRED returned no observations for {label}.")

    frame = pd.DataFrame(observations)
    if frame.empty or not {"date", "value"}.issubset(frame.columns):
        raise MacroDataError(f"FRED returned an unexpected payload for {label}.")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["value"] = pd.to_numeric(frame["value"].replace(".", pd.NA), errors="coerce")
    frame = frame.dropna(subset=["date", "value"]).sort_values("date")
    if frame.empty:
        raise MacroDataError(f"FRED returned no numeric observations for {label}.")

    series = frame.set_index("date")["value"]
    series.name = label
    return series


def _fetch_fred_series(
    series_id: str,
    label: str,
    api_key: str,
    session: requests.Session,
) -> pd.Series:
    response = session.get(
        FRED_OBSERVATIONS_URL,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": _start_date(),
        },
        timeout=30,
    )
    response.raise_for_status()
    return _series_from_observations(response.json(), label)


def _latest(series: pd.Series) -> float:
    return float(series.dropna().iloc[-1])


def _percentile(series: pd.Series) -> float:
    clean = series.dropna()
    latest = float(clean.iloc[-1])
    return float((clean <= latest).mean())


def _change(series: pd.Series, periods: int) -> float | None:
    clean = series.dropna()
    if len(clean) <= periods:
        return None
    return float(clean.iloc[-1] - clean.iloc[-periods - 1])


def analyze_macro(config: dict, session: requests.Session | None = None) -> dict:
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        return inactive_category(
            "macro",
            "Set FRED_API_KEY to activate free FRED macro indicators.",
        )

    series_config = config.get("macro_series", {})
    if not series_config:
        return inactive_category("macro", "No macro_series are configured.")

    session = session or requests.Session()
    series_by_key = {
        key: _fetch_fred_series(series_id, key, api_key, session)
        for key, series_id in series_config.items()
    }

    score = 0.0
    evidence: list[dict] = []
    metrics: dict[str, float | None] = {}

    def add(points: float, signal: str, detail: str) -> None:
        nonlocal score
        score += points
        evidence.append({"signal": signal, "points": points, "detail": detail})

    high_yield = series_by_key.get("high_yield_spread")
    if high_yield is not None:
        value = _latest(high_yield)
        percentile = _percentile(high_yield)
        metrics["high_yield_spread"] = round(value, 2)
        metrics["high_yield_spread_percentile"] = round(percentile, 4)
        if value >= 5 or percentile >= 0.9:
            add(25, "Credit spreads", f"High-yield spreads are elevated at {value:.2f}%.")
        elif value >= 4 or percentile >= 0.8:
            add(14, "Credit spreads", f"High-yield spreads are firm at {value:.2f}%.")

    vix = series_by_key.get("vix")
    if vix is not None:
        value = _latest(vix)
        percentile = _percentile(vix)
        metrics["vix"] = round(value, 2)
        metrics["vix_percentile"] = round(percentile, 4)
        if value >= 30 or percentile >= 0.9:
            add(22, "Equity volatility", f"VIX is elevated at {value:.1f}.")
        elif value >= 22 or percentile >= 0.8:
            add(12, "Equity volatility", f"VIX is firm at {value:.1f}.")

    ten_year = series_by_key.get("ten_year_yield")
    two_year = series_by_key.get("two_year_yield")
    if ten_year is not None:
        value = _latest(ten_year)
        change_3m = _change(ten_year, 63)
        metrics["ten_year_yield"] = round(value, 2)
        metrics["ten_year_yield_3m_change"] = round(change_3m, 2) if change_3m is not None else None
        if change_3m is not None and change_3m >= 0.75:
            add(18, "Rate shock", f"10-year Treasury yield rose {change_3m:.2f} points in roughly three months.")
        elif change_3m is not None and change_3m >= 0.4:
            add(9, "Rate shock", f"10-year Treasury yield rose {change_3m:.2f} points in roughly three months.")

    if ten_year is not None and two_year is not None:
        curve = _latest(ten_year) - _latest(two_year)
        metrics["ten_two_curve"] = round(curve, 2)
        if curve <= -0.75:
            add(12, "Yield curve", f"10Y-2Y curve is deeply inverted at {curve:.2f} points.")
        elif curve <= -0.25:
            add(6, "Yield curve", f"10Y-2Y curve is inverted at {curve:.2f} points.")

    financial_conditions = series_by_key.get("financial_conditions")
    if financial_conditions is not None:
        value = _latest(financial_conditions)
        percentile = _percentile(financial_conditions)
        metrics["financial_conditions"] = round(value, 3)
        metrics["financial_conditions_percentile"] = round(percentile, 4)
        if value >= 0.5 or percentile >= 0.9:
            add(20, "Financial conditions", f"Financial conditions are tight at {value:.2f}.")
        elif value >= 0 or percentile >= 0.8:
            add(10, "Financial conditions", f"Financial conditions are no longer easy at {value:.2f}.")

    return active_category(
        "macro",
        min(score, 100),
        0.8 if len(series_by_key) >= 4 else 0.65,
        metrics,
        evidence,
        "Free FRED macro indicators active.",
    )
