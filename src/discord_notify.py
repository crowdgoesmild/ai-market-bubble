from __future__ import annotations

import os
import requests


def maybe_notify(
    latest: dict,
    previous: dict | None,
    dashboard_url: str | None = None,
    alert_threshold_change: float = 5,
) -> None:
    webhook = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook:
        return

    changed_status = previous is None or previous.get("status") != latest["status"]
    score_change = (
        latest["score"] - previous.get("score", latest["score"])
        if previous
        else 0
    )

    if (
        previous is not None
        and not changed_status
        and abs(score_change) < alert_threshold_change
    ):
        return

    evidence = latest.get("evidence", [])[:4]
    lines = [
        f"**AI Bubble Monitor: {latest['status']}**",
        f"Score: **{latest['score']:.0f}/100**",
    ]

    if previous:
        lines.append(f"Change: **{score_change:+.0f} points**")

    if evidence:
        lines.append("")
        lines.append("Main triggered signals:")
        lines.extend(f"• {item['detail']}" for item in evidence)

    if dashboard_url:
        lines.extend(["", f"Dashboard: {dashboard_url}"])

    response = requests.post(
        webhook,
        json={"content": "\n".join(lines)},
        timeout=20,
    )
    response.raise_for_status()
