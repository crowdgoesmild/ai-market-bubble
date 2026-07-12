from __future__ import annotations

DEFAULT_STATUS_THRESHOLDS = {
    "normal": 25,
    "elevated": 40,
    "strained": 55,
    "high_risk": 70,
}


def score_market(metrics: dict) -> tuple[float, list[dict]]:
    score = 0.0
    evidence: list[dict] = []

    def add(points: float, signal: str, detail: str) -> None:
        nonlocal score
        score += points
        evidence.append({"signal": signal, "points": points, "detail": detail})

    below_50 = metrics["below_50_fraction"]
    below_200 = metrics["below_200_fraction"]
    drawdown = abs(min(metrics["basket_drawdown"], 0))
    vol_pct = metrics["volatility_percentile"]
    relative = metrics["relative_63d_vs_spy"]

    if below_50 >= 0.8:
        add(18, "Market breadth", f"{below_50:.0%} of the AI basket is below its 50-day average.")
    elif below_50 >= 0.6:
        add(12, "Market breadth", f"{below_50:.0%} of the AI basket is below its 50-day average.")
    elif below_50 >= 0.4:
        add(6, "Market breadth", f"{below_50:.0%} of the AI basket is below its 50-day average.")

    if below_200 >= 0.6:
        add(20, "Long-term trend", f"{below_200:.0%} of the basket is below its 200-day average.")
    elif below_200 >= 0.3:
        add(10, "Long-term trend", f"{below_200:.0%} of the basket is below its 200-day average.")

    if drawdown >= 0.25:
        add(20, "Drawdown", f"The equal-weight basket is {drawdown:.1%} below its peak.")
    elif drawdown >= 0.15:
        add(14, "Drawdown", f"The equal-weight basket is {drawdown:.1%} below its peak.")
    elif drawdown >= 0.08:
        add(7, "Drawdown", f"The equal-weight basket is {drawdown:.1%} below its peak.")

    if vol_pct >= 0.95:
        add(18, "Volatility", f"20-day volatility is in the {vol_pct:.0%} historical percentile.")
    elif vol_pct >= 0.85:
        add(10, "Volatility", f"20-day volatility is in the {vol_pct:.0%} historical percentile.")

    if relative <= -0.12:
        add(18, "Relative weakness", f"The basket trails SPY by {abs(relative):.1%} over roughly three months.")
    elif relative <= -0.06:
        add(10, "Relative weakness", f"The basket trails SPY by {abs(relative):.1%} over roughly three months.")

    return min(round(score, 1), 100.0), evidence


def status_for(score: float, thresholds: dict | None = None) -> str:
    limits = thresholds or DEFAULT_STATUS_THRESHOLDS

    if score < limits["normal"]:
        return "Normal"
    if score < limits["elevated"]:
        return "Elevated"
    if score < limits["strained"]:
        return "Strained"
    if score < limits["high_risk"]:
        return "High risk"
    return "Severe"
