import json
from datetime import datetime

from wypad import __main__ as cli
from wypad.run import WARSAW


def test_skip_if_done_does_not_search_again(tmp_path, monkeypatch, capsys):
    today = datetime.now(WARSAW).date().isoformat()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "deals.json").write_text(json.dumps({"date": today, "sample": False, "deals": []}))
    monkeypatch.setattr("wypad.run.search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not search")))
    assert cli.main(["search", "--site", str(tmp_path), "--state", str(tmp_path / "state"), "--skip-if-done"]) == 0
    assert "pomijam" in capsys.readouterr().out


def test_skip_if_done_still_searches_when_data_is_old_or_sample(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    called = []

    def fake_search(site, state, s):
        called.append(True)
        return {"deals": [], "stats": {"flight_options": 0, "duration_s": 0}}

    monkeypatch.setattr("wypad.run.search", fake_search)
    for payload in ({"date": "2000-01-01", "sample": False}, {"date": datetime.now(WARSAW).date().isoformat(), "sample": True}):
        (tmp_path / "data" / "deals.json").write_text(json.dumps(payload))
        assert cli.main(["search", "--site", str(tmp_path), "--state", str(tmp_path / "s"), "--skip-if-done"]) == 0
    assert called == [True, True]


def test_failed_search_returns_error_code(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("Brak danych o lotach")

    monkeypatch.setattr("wypad.run.search", boom)
    assert cli.main(["search", "--site", str(tmp_path), "--state", str(tmp_path / "s")]) == 2


def test_notify_skips_sample_data(tmp_path, capsys):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "deals.json").write_text(json.dumps({"sample": True, "deals": []}))
    assert cli.main(["notify", "--site", str(tmp_path)]) == 0
    assert "nie wysyłam" in capsys.readouterr().out
