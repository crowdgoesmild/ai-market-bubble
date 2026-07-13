from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go
from plotly.offline import plot


def _category_row(key: str, category: dict) -> str:
    label = category.get("label", key)
    if category.get("active"):
        score = f"{category['score']:.0f}/100"
        confidence = f"{category.get('confidence', 0):.0%}"
    else:
        score = "Inactive"
        confidence = "0%"

    return (
        "<tr>"
        f"<td>{label}</td>"
        f"<td>{score}</td>"
        f"<td>{confidence}</td>"
        f"<td>{category.get('message', '')}</td>"
        "</tr>"
    )


def build_dashboard(latest: dict, history: list[dict], output_path: Path) -> None:
    dates = [row["date"] for row in history]
    scores = [row["score"] for row in history]

    score_chart = go.Figure()
    score_chart.add_trace(
        go.Scatter(x=dates, y=scores, mode="lines+markers", name="Stress score")
    )
    score_chart.update_layout(
        title="Stress score history",
        yaxis={"range": [0, 100], "title": "Score"},
        xaxis={"title": "Date"},
        margin={"l": 45, "r": 20, "t": 55, "b": 45},
        height=360,
    )

    basket = latest["market"]["basket_history"]
    basket_chart = go.Figure()
    basket_chart.add_trace(
        go.Scatter(
            x=[row["date"] for row in basket],
            y=[row["value"] for row in basket],
            mode="lines",
            name="Equal-weight AI basket",
        )
    )
    basket_chart.update_layout(
        title="AI basket index, recent 180 sessions",
        margin={"l": 45, "r": 20, "t": 55, "b": 45},
        height=360,
    )

    category_rows = "".join(
        _category_row(key, category)
        for key, category in latest.get("categories", {}).items()
    )

    evidence_rows = "".join(
        "<tr>"
        f"<td>{item.get('category', 'Market')}</td>"
        f"<td>{item['signal']}</td>"
        f"<td>+{item['points']}</td>"
        f"<td>{item['detail']}</td>"
        "</tr>"
        for item in latest["evidence"]
    ) or "<tr><td colspan='4'>No stress thresholds triggered.</td></tr>"

    ticker_rows = "".join(
        "<tr>"
        f"<td>{row['ticker']}</td>"
        f"<td>{row['price']}</td>"
        f"<td>{'Yes' if row['below_50dma'] else 'No'}</td>"
        f"<td>{'Yes' if row['below_200dma'] else 'No'}</td>"
        + (
            f"<td>{row['drawdown_52w']:.1%}</td>"
            if row["drawdown_52w"] is not None
            else "<td>Unavailable</td>"
        )
        + "</tr>"
        for row in latest["market"]["tickers"]
    )

    html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI Bubble Stress Monitor</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 0; background: #f4f5f7; color: #202124; }}
main {{ max-width: 1100px; margin: auto; padding: 24px; }}
header {{ display:flex; justify-content:space-between; gap:24px; align-items:center; flex-wrap:wrap; }}
.card {{ background:white; border-radius:14px; padding:20px; margin:16px 0; box-shadow:0 2px 10px rgba(0,0,0,.06); }}
.score {{ font-size:54px; font-weight:750; }}
.status {{ font-size:20px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:10px; border-bottom:1px solid #e5e7eb; }}
small {{ color:#6b7280; }}
.metric {{ font-size:25px; font-weight:700; }}
</style>
</head>
<body>
<main>
<header>
<div>
<h1>AI Bubble Stress Monitor</h1>
<p>Transparent market-stress signals, not a crystal ball.</p>
</div>
<div class="card">
<div class="score">{latest['score']:.0f}/100</div>
<div class="status">{latest['status']}</div>
<small>Confidence {latest['confidence']:.0%} · Updated {latest['as_of']}</small>
</div>
</header>

<div class="grid">
<div class="card"><div class="metric">{latest['market']['below_50_fraction']:.0%}</div><small>Basket below 50-day average</small></div>
<div class="card"><div class="metric">{latest['market']['below_200_fraction']:.0%}</div><small>Basket below 200-day average</small></div>
<div class="card"><div class="metric">{latest['market']['basket_drawdown']:.1%}</div><small>Basket drawdown</small></div>
<div class="card"><div class="metric">{latest['market']['relative_63d_vs_spy']:.1%}</div><small>Approx. 3-month return versus SPY</small></div>
</div>

<div class="card">
<h2>Signal categories</h2>
<table><thead><tr><th>Category</th><th>Score</th><th>Confidence</th><th>Status</th></tr></thead><tbody>{category_rows}</tbody></table>
</div>

<div class="grid">
<div class="card">{plot(score_chart, include_plotlyjs='cdn', output_type='div')}</div>
<div class="card">{plot(basket_chart, include_plotlyjs=False, output_type='div')}</div>
</div>

<div class="card">
<h2>Triggered evidence</h2>
<table><thead><tr><th>Category</th><th>Signal</th><th>Points</th><th>Evidence</th></tr></thead><tbody>{evidence_rows}</tbody></table>
</div>

<div class="card">
<h2>Basket detail</h2>
<table><thead><tr><th>Ticker</th><th>Price</th><th>Below 50DMA</th><th>Below 200DMA</th><th>52-week drawdown</th></tr></thead>
<tbody>{ticker_rows}</tbody></table>
</div>

<div class="card">
<small>Market source: {latest['market'].get('source', 'Unknown')}. Free non-price sources are shown as active only when their required public data is available.</small>
</div>
</main>
</body>
</html>'''

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
