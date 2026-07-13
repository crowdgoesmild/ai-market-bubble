from __future__ import annotations

import html
import os
import re
import time

import requests

from .category_scoring import active_category, inactive_category

SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _sec_user_agent() -> str:
    return os.getenv("SEC_USER_AGENT") or "ai-bubble-monitor/0.2 contact@example.com"


def _normalise_cik(cik: str | int) -> str:
    return str(cik).zfill(10)


def _headers() -> dict[str, str]:
    return {"User-Agent": _sec_user_agent(), "Accept-Encoding": "gzip, deflate"}


def _latest_primary_filing(cik: str, session: requests.Session) -> dict | None:
    response = session.get(
        SEC_SUBMISSIONS_URL.format(cik=_normalise_cik(cik)),
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    recent = response.json().get("filings", {}).get("recent", {})

    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    filing_dates = recent.get("filingDate", [])

    for form, accession, document, filing_date in zip(forms, accessions, primary_docs, filing_dates, strict=False):
        if form in {"10-K", "10-Q"} and accession and document:
            return {
                "form": form,
                "accession": accession,
                "document": document,
                "filing_date": filing_date,
            }
    return None


def _filing_text(cik: str, filing: dict, session: requests.Session) -> str:
    response = session.get(
        SEC_ARCHIVES_URL.format(
            cik=str(int(cik)),
            accession=filing["accession"].replace("-", ""),
            document=filing["document"],
        ),
        headers=_headers(),
        timeout=30,
    )
    response.raise_for_status()
    text = TAG_RE.sub(" ", response.text)
    text = html.unescape(text)
    return WHITESPACE_RE.sub(" ", text).lower()


def _term_count(text: str, terms: list[str]) -> int:
    return sum(text.count(term.lower()) for term in terms)


def analyze_filing_language(config: dict, session: requests.Session | None = None) -> dict:
    cik_by_ticker = config.get("sec_companies", {})
    tickers = [ticker for ticker in config.get("ai_basket", []) if ticker in cik_by_ticker]
    if not tickers:
        return inactive_category("capex_narrative", "No SEC company CIKs are configured for filing-language checks.")

    language_config = config.get("filing_language", {})
    ai_terms = language_config.get("ai_terms", [])
    risk_terms = language_config.get("risk_terms", [])
    capex_terms = language_config.get("capex_terms", [])
    if not ai_terms and not risk_terms and not capex_terms:
        return inactive_category("capex_narrative", "No filing-language terms are configured.")

    session = session or requests.Session()
    rows = []
    errors = []

    for ticker in tickers:
        cik = cik_by_ticker[ticker]
        try:
            filing = _latest_primary_filing(cik, session)
            if not filing:
                errors.append(f"{ticker}: no recent 10-K/10-Q filing")
                continue

            text = _filing_text(cik, filing, session)
            words = max(len(text.split()), 1)
            ai_count = _term_count(text, ai_terms)
            risk_count = _term_count(text, risk_terms)
            capex_count = _term_count(text, capex_terms)
            rows.append(
                {
                    "ticker": ticker,
                    "form": filing["form"],
                    "filing_date": filing["filing_date"],
                    "word_count": words,
                    "ai_mentions_per_10k_words": round(ai_count / words * 10000, 2),
                    "risk_mentions_per_10k_words": round(risk_count / words * 10000, 2),
                    "capex_mentions_per_10k_words": round(capex_count / words * 10000, 2),
                }
            )
        except requests.RequestException as exc:
            errors.append(f"{ticker}: {exc}")
        time.sleep(0.2)

    if not rows:
        return inactive_category("capex_narrative", "Filing language unavailable: " + "; ".join(errors[:4]))

    avg_risk_density = sum(row["risk_mentions_per_10k_words"] for row in rows) / len(rows)
    avg_capex_density = sum(row["capex_mentions_per_10k_words"] for row in rows) / len(rows)
    avg_ai_density = sum(row["ai_mentions_per_10k_words"] for row in rows) / len(rows)

    score = 0.0
    evidence: list[dict] = []

    def add(points: float, signal: str, detail: str) -> None:
        nonlocal score
        score += points
        evidence.append({"signal": signal, "points": points, "detail": detail})

    if avg_risk_density >= 20:
        add(25, "Risk language", f"Risk-language density averages {avg_risk_density:.1f} mentions per 10k words.")
    elif avg_risk_density >= 10:
        add(12, "Risk language", f"Risk-language density averages {avg_risk_density:.1f} mentions per 10k words.")

    if avg_capex_density >= 12:
        add(18, "Capex narrative", f"Capex-language density averages {avg_capex_density:.1f} mentions per 10k words.")

    if avg_ai_density >= 30 and avg_risk_density >= 10:
        add(12, "AI risk narrative", "AI language and risk language are both prominent in recent filings.")

    metrics = {
        "covered_filings": len(rows),
        "configured_companies": len(tickers),
        "average_ai_mentions_per_10k_words": round(avg_ai_density, 2),
        "average_risk_mentions_per_10k_words": round(avg_risk_density, 2),
        "average_capex_mentions_per_10k_words": round(avg_capex_density, 2),
        "filings": rows,
        "errors": errors[:5],
    }
    confidence = min(0.75, 0.35 + 0.4 * len(rows) / max(len(tickers), 1))

    return active_category(
        "capex_narrative",
        min(score, 100),
        confidence,
        metrics,
        evidence,
        "Free SEC filing-language checks active.",
    )
