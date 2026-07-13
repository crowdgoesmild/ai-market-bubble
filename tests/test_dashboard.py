from __future__ import annotations

from src.dashboard import build_dashboard


def test_build_dashboard_writes_static_html(tmp_path) -> None:
    latest = {
        "as_of": "2026-01-02",
        "score": 12,
        "status": "Normal",
        "confidence": 0.55,
        "evidence": [],
        "categories": {
            "market": {
                "label": "Market price",
                "active": True,
                "score": 12,
                "confidence": 1.0,
                "message": "Test market indicators active.",
            },
            "macro": {
                "label": "Macro",
                "active": False,
                "score": None,
                "confidence": 0.0,
                "message": "No key.",
            },
        },
        "market": {
            "source": "Test fixture",
            "below_50_fraction": 0.25,
            "below_200_fraction": 0.0,
            "basket_drawdown": -0.04,
            "relative_63d_vs_spy": 0.02,
            "basket_history": [
                {"date": "2026-01-01", "value": 1.0},
                {"date": "2026-01-02", "value": 1.01},
            ],
            "tickers": [
                {
                    "ticker": "AAA",
                    "price": 101.25,
                    "below_50dma": False,
                    "below_200dma": False,
                    "drawdown_52w": -0.04,
                }
            ],
        },
    }
    history = [
        {"date": "2026-01-01", "score": 14, "status": "Normal"},
        {"date": "2026-01-02", "score": 12, "status": "Normal"},
    ]
    output_path = tmp_path / "index.html"

    build_dashboard(latest, history, output_path)

    html = output_path.read_text(encoding="utf-8")
    assert "AI Bubble Stress Monitor" in html
    assert "Signal categories" in html
    assert "No stress thresholds triggered" in html
    assert "AAA" in html
