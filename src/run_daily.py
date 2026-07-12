from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .config import DATA_DIR, DOCS_DIR, load_config
from .dashboard import build_dashboard
from .discord_notify import maybe_notify
from .market import MarketDataError, calculate_market_metrics, download_prices
from .scoring import score_market, status_for


def read_json(path):
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    config = load_config()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    latest_path = DATA_DIR / "latest.json"
    history_path = DATA_DIR / "score_history.json"
    previous = read_json(latest_path)
    history = read_json(history_path) or []

    prices = download_prices(
        config["tickers"],
        provider=config.get("market_data_provider", "tiingo"),
    )
    market = calculate_market_metrics(
        prices,
        config["ai_basket"],
        config["benchmark"],
    )
    market_score, evidence = score_market(market)

    confidence = 0.55

    latest = {
        "as_of": market["as_of"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": market_score,
        "status": status_for(market_score, config.get("status_thresholds")),
        "confidence": confidence,
        "category_scores": {
            "market": market_score,
            "fundamentals": None,
            "capex_narrative": None,
            "adoption": None,
            "macro": None,
            "private_market": None,
        },
        "market": market,
        "evidence": evidence,
    }

    history = [
        row for row in history
        if row.get("date") != latest["as_of"]
    ]
    history.append(
        {
            "date": latest["as_of"],
            "score": latest["score"],
            "status": latest["status"],
        }
    )
    history = sorted(history, key=lambda row: row["date"])[-1000:]

    latest_path.write_text(
        json.dumps(latest, indent=2),
        encoding="utf-8",
    )
    history_path.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8",
    )
    (DOCS_DIR / "data.json").write_text(
        json.dumps(latest, indent=2),
        encoding="utf-8",
    )

    build_dashboard(
        latest,
        history,
        DOCS_DIR / "index.html",
    )

    maybe_notify(
        latest,
        previous,
        dashboard_url=os.getenv("DASHBOARD_URL"),
        alert_threshold_change=config.get("alert_threshold_change", 5),
    )

    print(
        f"AI bubble stress score: "
        f"{latest['score']:.0f}/100 ({latest['status']})"
    )
    print(f"Dashboard written to {DOCS_DIR / 'index.html'}")


if __name__ == "__main__":
    try:
        main()
    except MarketDataError as exc:
        raise SystemExit(f"Market data error: {exc}") from None
