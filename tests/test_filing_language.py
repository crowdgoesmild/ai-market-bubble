from __future__ import annotations

from src.filing_language import analyze_filing_language


class FakeResponse:
    def __init__(self, payload=None, text: str = "") -> None:
        self.payload = payload
        self.text = text

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class FakeSession:
    def get(self, url, headers, timeout):
        if "submissions" in url:
            return FakeResponse(
                {
                    "filings": {
                        "recent": {
                            "form": ["10-Q"],
                            "accessionNumber": ["0000000000-26-000001"],
                            "primaryDocument": ["filing.htm"],
                            "filingDate": ["2026-03-31"],
                        }
                    }
                }
            )
        text = " ".join(["artificial intelligence"] * 40 + ["uncertain demand"] * 30 + ["capital expenditures"] * 20)
        return FakeResponse(text=f"<html><body>{text}</body></html>")


def test_analyze_filing_language_scores_recent_sec_filing() -> None:
    result = analyze_filing_language(
        {
            "ai_basket": ["AAA"],
            "sec_companies": {"AAA": "1"},
            "filing_language": {
                "ai_terms": ["artificial intelligence"],
                "risk_terms": ["uncertain demand"],
                "capex_terms": ["capital expenditures"],
            },
        },
        FakeSession(),
    )

    assert result["active"] is True
    assert result["score"] > 0
    assert result["metrics"]["covered_filings"] == 1
