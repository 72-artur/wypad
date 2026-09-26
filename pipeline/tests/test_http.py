import pytest
import requests

from wypad import http as http_mod
from wypad.http import Http


class Resp:
    def __init__(self, status, payload=None):
        self.status_code, self.payload = status, payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self):
        return self.payload


class Script:
    def __init__(self, statuses):
        self.statuses, self.calls = list(statuses), 0

    def request(self, method, url, timeout, **kw):
        self.calls += 1
        return Resp(self.statuses.pop(0), {"ok": True})


def make(statuses, monkeypatch, retries=3):
    sleeps = []
    monkeypatch.setattr(http_mod.time, "sleep", lambda s: sleeps.append(s))
    h = Http(delay_s=0, retries=retries)
    h.s = Script(statuses)
    return h, sleeps


def test_client_errors_are_not_retried(monkeypatch):
    h, sleeps = make([400, 200], monkeypatch)
    with pytest.raises(RuntimeError, match="after 1 attempt"):
        h.post_json("https://x", {})
    assert h.s.calls == 1 and sleeps == []


def test_server_errors_are_retried_then_succeed(monkeypatch):
    h, sleeps = make([503, 200], monkeypatch)
    assert h.get_json("https://x") == {"ok": True}
    assert h.s.calls == 2 and sleeps == [3]


def test_no_pointless_sleep_after_the_last_attempt(monkeypatch):
    h, sleeps = make([503, 503], monkeypatch, retries=2)
    with pytest.raises(RuntimeError, match="after 2 attempt"):
        h.get_json("https://x")
    assert sleeps == [3]
