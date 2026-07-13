from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from .adoption import analyze_adoption
from .category_scoring import active_category, combine_category_scores, inactive_category, safe_category
from .config import DATA_DIR, DOCS_DIR, load_config
from .dashboard import build_dashboard
from .discord_notify import maybe_notify
from .filing_language import analyze_filing_language
from .fundamentals import analyze_fundamentals
from .macro import analyze_macro
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

    categories = {
        "market": active_category(
            "market",
            market_score,
            1.0,
            market,
            evidence,
            "Tiingo daily adjusted-price indicators active.",
        ),
        "fundamentals": safe_category("fundamentals", analyze_fundamentals, config),
        "capex_narrative": safe_category("capex_narrative", analyze_filing_language, config),
        "adoption": safe_category("adoption", analyze_adoption, config),
        "macro": safe_category("macro", analyze_macro, config),
        "private_market": inactive_category(
            "private_market",
            "No reliable free structured private-market source is configured.",
        ),
    }
    score, confidence, category_scores, combined_evidence = combine_category_scores(
        config["weights"],
        categories,
    )

    latest = {
        "as_of": market["as_of"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "score": score,
        "status": status_for(score, config.get("status_thresholds")),
        "confidence": confidence,
        "category_scores": category_scores,
        "categories": categories,
        "market": market,
        "evidence": combined_evidence,
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
