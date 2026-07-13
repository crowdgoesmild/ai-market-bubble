from __future__ import annotations

from typing import Any

CATEGORY_LABELS = {
    "market": "Market price",
    "fundamentals": "Fundamentals",
    "capex_narrative": "Filing language",
    "adoption": "Adoption",
    "macro": "Macro",
    "private_market": "Private market",
}


def inactive_category(category: str, reason: str) -> dict[str, Any]:
    return {
        "category": category,
        "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
        "active": False,
        "score": None,
        "confidence": 0.0,
        "metrics": {},
        "evidence": [],
        "message": reason,
    }


def active_category(
    category: str,
    score: float,
    confidence: float,
    metrics: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "category": category,
        "label": CATEGORY_LABELS.get(category, category.replace("_", " ").title()),
        "active": True,
        "score": min(max(round(score, 1), 0.0), 100.0),
        "confidence": min(max(round(confidence, 2), 0.0), 1.0),
        "metrics": metrics or {},
        "evidence": evidence or [],
        "message": message or "",
    }


def safe_category(category: str, analyze, *args, **kwargs) -> dict[str, Any]:
    try:
        return analyze(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - non-market categories should not break the daily run.
        return inactive_category(category, f"{CATEGORY_LABELS.get(category, category)} unavailable: {exc}")


def combine_category_scores(
    weights: dict[str, float],
    categories: dict[str, dict[str, Any]],
) -> tuple[float, float, dict[str, float | None], list[dict[str, Any]]]:
    active_categories = {
        key: value
        for key, value in categories.items()
        if value.get("active") and value.get("score") is not None
    }
    active_weight = sum(weights.get(key, 0.0) for key in active_categories)

    if active_weight <= 0:
        score = 0.0
        confidence = 0.0
    else:
        score = sum(
            float(category["score"]) * weights.get(key, 0.0)
            for key, category in active_categories.items()
        ) / active_weight
        weighted_confidence = sum(
            float(category.get("confidence", 0.0)) * weights.get(key, 0.0)
            for key, category in active_categories.items()
        ) / active_weight
        confidence = min(0.95, 0.3 + 0.7 * active_weight * weighted_confidence)

    category_scores = {
        key: (category.get("score") if category.get("active") else None)
        for key, category in categories.items()
    }

    evidence = []
    for key, category in categories.items():
        label = category.get("label") or CATEGORY_LABELS.get(key, key)
        for item in category.get("evidence", []):
            evidence.append({"category": label, **item})

    return round(score, 1), round(confidence, 2), category_scores, evidence
