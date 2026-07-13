from __future__ import annotations

from src.fundamentals import analyze_fundamentals


def fact(value: float, start: str, end: str, fy: int, fp: str) -> dict:
    return {
        "val": value,
        "start": start,
        "end": end,
        "fy": fy,
        "fp": fp,
        "form": "10-Q",
        "filed": end,
    }


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        revenues = [
            fact(100, "2025-01-01", "2025-03-31", 2025, "Q1"),
            fact(100, "2025-04-01", "2025-06-30", 2025, "Q2"),
            fact(100, "2025-07-01", "2025-09-30", 2025, "Q3"),
            fact(100, "2025-10-01", "2025-12-31", 2025, "Q4"),
            fact(80, "2026-01-01", "2026-03-31", 2026, "Q1"),
        ]
        return {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": revenues}},
                    "OperatingIncomeLoss": {"units": {"USD": [fact(2, "2026-01-01", "2026-03-31", 2026, "Q1")]}},
                    "PaymentsToAcquirePropertyPlantAndEquipment": {
                        "units": {"USD": [fact(30, "2026-01-01", "2026-03-31", 2026, "Q1")]}
                    },
                }
            }
        }


class FakeSession:
    def get(self, url, headers, timeout):
        return FakeResponse()


def test_analyze_fundamentals_scores_sec_companyfacts() -> None:
    result = analyze_fundamentals(
        {
            "ai_basket": ["AAA"],
            "sec_companies": {"AAA": "1"},
        },
        FakeSession(),
    )

    assert result["active"] is True
    assert result["score"] > 0
    assert result["metrics"]["company_rows"][0]["revenue_yoy"] == -0.2
