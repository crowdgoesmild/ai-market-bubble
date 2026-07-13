from __future__ import annotations

from src.adoption import analyze_adoption


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def get(self, url, headers, timeout):
        if "api.github.com" in url:
            return FakeResponse(
                {
                    "stargazers_count": 100,
                    "forks_count": 10,
                    "open_issues_count": 2,
                    "pushed_at": "2026-07-01T00:00:00Z",
                }
            )
        return FakeResponse(
            {
                "downloads": 1000,
                "likes": 100,
                "lastModified": "2026-07-01T00:00:00Z",
            }
        )


def test_analyze_adoption_uses_public_repos_and_models() -> None:
    result = analyze_adoption(
        {
            "adoption": {
                "github_repositories": ["example/repo"],
                "huggingface_models": ["example/model"],
            }
        },
        FakeSession(),
    )

    assert result["active"] is True
    assert result["score"] == 0
    assert result["metrics"]["github_repositories"][0]["stars"] == 100
    assert result["metrics"]["huggingface_models"][0]["downloads"] == 1000
