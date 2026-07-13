from __future__ import annotations

from datetime import datetime, timezone
import os

import requests

from .category_scoring import active_category, inactive_category

GITHUB_REPO_URL = "https://api.github.com/repos/{repo}"
HF_MODEL_URL = "https://huggingface.co/api/models/{model_id}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _days_since(value: str | None) -> int | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return (datetime.now(timezone.utc) - parsed).days


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _hf_headers() -> dict[str, str]:
    headers = {"Accept": "application/json"}
    token = os.getenv("HF_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def analyze_adoption(config: dict, session: requests.Session | None = None) -> dict:
    adoption_config = config.get("adoption", {})
    github_repos = adoption_config.get("github_repositories", [])
    hf_models = adoption_config.get("huggingface_models", [])

    if not github_repos and not hf_models:
        return inactive_category("adoption", "No public adoption proxies are configured.")

    session = session or requests.Session()
    github_rows = []
    hf_rows = []
    errors = []

    for repo in github_repos:
        try:
            response = session.get(GITHUB_REPO_URL.format(repo=repo), headers=_github_headers(), timeout=20)
            response.raise_for_status()
            payload = response.json()
            days = _days_since(payload.get("pushed_at"))
            github_rows.append(
                {
                    "repository": repo,
                    "stars": payload.get("stargazers_count"),
                    "forks": payload.get("forks_count"),
                    "open_issues": payload.get("open_issues_count"),
                    "days_since_push": days,
                }
            )
        except requests.RequestException as exc:
            errors.append(f"{repo}: {exc}")

    for model_id in hf_models:
        try:
            response = session.get(HF_MODEL_URL.format(model_id=model_id), headers=_hf_headers(), timeout=20)
            response.raise_for_status()
            payload = response.json()
            days = _days_since(payload.get("lastModified"))
            hf_rows.append(
                {
                    "model": model_id,
                    "downloads": payload.get("downloads"),
                    "likes": payload.get("likes"),
                    "days_since_modified": days,
                }
            )
        except requests.RequestException as exc:
            errors.append(f"{model_id}: {exc}")

    if not github_rows and not hf_rows:
        return inactive_category("adoption", "Public adoption proxies unavailable: " + "; ".join(errors[:4]))

    score = 0.0
    evidence: list[dict] = []

    def add(points: float, signal: str, detail: str) -> None:
        nonlocal score
        score += points
        evidence.append({"signal": signal, "points": points, "detail": detail})

    github_activity = [
        row["days_since_push"] is not None and row["days_since_push"] <= 120
        for row in github_rows
    ]
    hf_activity = [
        row["days_since_modified"] is not None and row["days_since_modified"] <= 180
        for row in hf_rows
    ]

    if github_activity:
        active_fraction = sum(github_activity) / len(github_activity)
        if active_fraction < 0.5:
            add(25, "Open-source activity", f"Only {active_fraction:.0%} of tracked AI repos were updated recently.")
        elif active_fraction < 0.75:
            add(12, "Open-source activity", f"{active_fraction:.0%} of tracked AI repos were updated recently.")

    if hf_activity:
        active_fraction = sum(hf_activity) / len(hf_activity)
        if active_fraction < 0.5:
            add(20, "Model activity", f"Only {active_fraction:.0%} of tracked Hugging Face models changed recently.")
        elif active_fraction < 0.75:
            add(10, "Model activity", f"{active_fraction:.0%} of tracked Hugging Face models changed recently.")

    metrics = {
        "github_repositories": github_rows,
        "huggingface_models": hf_rows,
        "errors": errors[:5],
    }
    configured_count = len(github_repos) + len(hf_models)
    covered_count = len(github_rows) + len(hf_rows)
    confidence = min(0.75, 0.35 + 0.4 * covered_count / max(configured_count, 1))

    return active_category(
        "adoption",
        min(score, 100),
        confidence,
        metrics,
        evidence,
        "Free public adoption proxies active.",
    )
