from __future__ import annotations

import os
import time

import pandas as pd
import requests

from .category_scoring import active_category, inactive_category

SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet",
    "Revenues",
)
OPERATING_INCOME_CONCEPTS = ("OperatingIncomeLoss",)
CAPEX_CONCEPTS = ("PaymentsToAcquirePropertyPlantAndEquipment",)


class FundamentalsDataError(RuntimeError):
    """Raised when SEC fundamentals cannot be obtained or validated."""


def _sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT") or "ai-bubble-monitor/0.2 contact@example.com"


def _normalise_cik(cik: str | int) -> str:
    return str(cik).zfill(10)


def _quarterly_facts(companyfacts: dict, concepts: tuple[str, ...]) -> list[dict]:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    entries: list[dict] = []

    for concept in concepts:
        concept_facts = facts.get(concept, {}).get("units", {}).get("USD", [])
        for item in concept_facts:
            if item.get("form") not in {"10-Q", "10-K"}:
                continue
            if "start" not in item or "end" not in item:
                continue

            start = pd.to_datetime(item.get("start"), errors="coerce")
            end = pd.to_datetime(item.get("end"), errors="coerce")
            value = pd.to_numeric(item.get("val"), errors="coerce")
            if pd.isna(start) or pd.isna(end) or pd.isna(value):
                continue

            duration = (end - start).days
            if not 70 <= duration <= 120:
                continue

            entries.append(
                {
                    "concept": concept,
                    "end": end,
                    "filed": item.get("filed"),
                    "fy": item.get("fy"),
                    "fp": item.get("fp"),
                    "value": float(value),
                }
            )

        if entries:
            break

    deduped = {
        (entry["end"], entry.get("fp")): entry
        for entry in sorted(entries, key=lambda row: (row["end"], row.get("filed") or ""))
    }
    return sorted(deduped.values(), key=lambda row: row["end"])


def _latest_and_year_ago(entries: list[dict]) -> tuple[dict | None, dict | None]:
    if not entries:
        return None, None

    latest = entries[-1]
    year_ago = entries[-5] if len(entries) >= 5 else None
    return latest, year_ago


def _fetch_companyfacts(cik: str, session: requests.Session) -> dict:
    response = session.get(
        SEC_COMPANYFACTS_URL.format(cik=_normalise_cik(cik)),
        headers={"User-Agent": _sec_user_agent(), "Accept-Encoding": "gzip, deflate"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _company_metrics(ticker: str, companyfacts: dict) -> dict | None:
    revenue_entries = _quarterly_facts(companyfacts, REVENUE_CONCEPTS)
    revenue_latest, revenue_year_ago = _latest_and_year_ago(revenue_entries)
    if revenue_latest is None:
        return None

    operating_entries = _quarterly_facts(companyfacts, OPERATING_INCOME_CONCEPTS)
    operating_latest, _ = _latest_and_year_ago(operating_entries)
    capex_entries = _quarterly_facts(companyfacts, CAPEX_CONCEPTS)
    capex_latest, _ = _latest_and_year_ago(capex_entries)

    revenue = revenue_latest["value"]
    revenue_yoy = None
    if revenue_year_ago and revenue_year_ago["value"] != 0:
        revenue_yoy = revenue / revenue_year_ago["value"] - 1

    operating_margin = None
    if operating_latest and revenue:
        operating_margin = operating_latest["value"] / revenue

    capex_to_revenue = None
    if capex_latest and revenue:
        capex_to_revenue = abs(capex_latest["value"]) / revenue

    return {
        "ticker": ticker,
        "period_end": revenue_latest["end"].date().isoformat(),
        "revenue": round(revenue, 0),
        "revenue_yoy": round(revenue_yoy, 4) if revenue_yoy is not None else None,
        "operating_margin": round(operating_margin, 4) if operating_margin is not None else None,
        "capex_to_revenue": round(capex_to_revenue, 4) if capex_to_revenue is not None else None,
    }


def analyze_fundamentals(config: dict, session: requests.Session | None = None) -> dict:
    cik_by_ticker = config.get("sec_companies", {})
    tickers = [ticker for ticker in config.get("ai_basket", []) if ticker in cik_by_ticker]
    if not tickers:
        return inactive_category("fundamentals", "No SEC company CIKs are configured for the AI basket.")

    session = session or requests.Session()
    company_rows = []
    errors = []

    for ticker in tickers:
        try:
            row = _company_metrics(ticker, _fetch_companyfacts(cik_by_ticker[ticker], session))
            if row:
                company_rows.append(row)
            else:
                errors.append(f"{ticker}: no comparable quarterly revenue facts")
        except (requests.RequestException, FundamentalsDataError, ValueError) as exc:
            errors.append(f"{ticker}: {exc}")
        time.sleep(0.2)

    if not company_rows:
        return inactive_category("fundamentals", "SEC fundamentals unavailable: " + "; ".join(errors[:4]))

    revenue_yoy = [row["revenue_yoy"] for row in company_rows if row["revenue_yoy"] is not None]
    margins = [row["operating_margin"] for row in company_rows if row["operating_margin"] is not None]
    capex_ratios = [row["capex_to_revenue"] for row in company_rows if row["capex_to_revenue"] is not None]

    score = 0.0
    evidence: list[dict] = []

    def add(points: float, signal: str, detail: str) -> None:
        nonlocal score
        score += points
        evidence.append({"signal": signal, "points": points, "detail": detail})

    if revenue_yoy:
        declining_fraction = sum(value < 0 for value in revenue_yoy) / len(revenue_yoy)
        slow_fraction = sum(value < 0.1 for value in revenue_yoy) / len(revenue_yoy)
        if declining_fraction >= 0.3:
            add(28, "Revenue deterioration", f"{declining_fraction:.0%} of covered companies have falling revenue.")
        elif slow_fraction >= 0.5:
            add(14, "Revenue slowdown", f"{slow_fraction:.0%} of covered companies have revenue growth below 10%.")

    if margins:
        weak_margin_fraction = sum(value < 0.05 for value in margins) / len(margins)
        if weak_margin_fraction >= 0.25:
            add(18, "Margin pressure", f"{weak_margin_fraction:.0%} of covered companies have operating margin below 5%.")

    if capex_ratios:
        heavy_capex_fraction = sum(value > 0.25 for value in capex_ratios) / len(capex_ratios)
        if heavy_capex_fraction >= 0.3:
            add(18, "Capex intensity", f"{heavy_capex_fraction:.0%} of covered companies have capex above 25% of revenue.")

    metrics = {
        "covered_companies": len(company_rows),
        "configured_companies": len(tickers),
        "company_rows": company_rows,
        "errors": errors[:5],
    }

    confidence = min(0.85, 0.45 + 0.4 * len(company_rows) / max(len(tickers), 1))
    return active_category(
        "fundamentals",
        min(score, 100),
        confidence,
        metrics,
        evidence,
        "Free SEC companyfacts fundamentals active.",
    )
