from __future__ import annotations

from src.category_scoring import active_category, combine_category_scores, inactive_category


def test_combine_category_scores_normalizes_active_weights() -> None:
    categories = {
        "market": active_category("market", 50, 1.0),
        "macro": inactive_category("macro", "No key."),
    }
    weights = {"market": 0.35, "macro": 0.1}

    score, confidence, category_scores, evidence = combine_category_scores(weights, categories)

    assert score == 50
    assert confidence == 0.54
    assert category_scores == {"market": 50, "macro": None}
    assert evidence == []
