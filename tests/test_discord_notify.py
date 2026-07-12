from __future__ import annotations

from src.discord_notify import maybe_notify


class FakeResponse:
    def raise_for_status(self) -> None:
        return None


def test_maybe_notify_uses_configured_change_threshold(monkeypatch) -> None:
    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeResponse()

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.test/webhook")
    monkeypatch.setattr("src.discord_notify.requests.post", fake_post)

    previous = {"score": 10, "status": "Normal"}
    latest = {"score": 13, "status": "Normal", "evidence": []}

    maybe_notify(latest, previous, alert_threshold_change=5)
    assert calls == []

    maybe_notify(latest, previous, alert_threshold_change=2)
    assert len(calls) == 1
