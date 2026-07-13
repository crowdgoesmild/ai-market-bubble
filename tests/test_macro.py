from __future__ import annotations

from src.macro import analyze_macro


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def get(self, url, params, timeout):
        observations = [
            {"date": "2026-01-01", "value": "10"},
            {"date": "2026-01-02", "value": "20"},
            {"date": "2026-01-03", "value": "30"},
        ]
        return FakeResponse({"observations": observations})


def test_analyze_macro_is_inactive_without_fred_key(monkeypatch) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    result = analyze_macro({"macro_series": {"vix": "VIXCLS"}}, FakeSession())

    assert result["active"] is False
    assert "FRED_API_KEY" in result["message"]


def test_analyze_macro_scores_configured_series(monkeypatch) -> None:
    monkeypatch.setenv("FRED_API_KEY", "test")

    result = analyze_macro({"macro_series": {"vix": "VIXCLS"}}, FakeSession())

    assert result["active"] is True
    assert result["score"] > 0
    assert result["metrics"]["vix"] == 30
