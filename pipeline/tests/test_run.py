"""End-to-end run of search() with fake sources: what gets published, and that failures publish nothing."""
import json
from datetime import date, datetime, timedelta

import pytest

from wypad.config import Settings
from wypad.run import WARSAW, search

NOW = datetime(2026, 9, 25, 6, 30, tzinfo=WARSAW)
DESTS = ("BCN", "BGY", "LIS", "CIA")


def combo(dest, day, fare_total):
    out = date(2026, 10, day)
    back = out + timedelta(days=3)
    return {"carrier": "Ryanair", "carrier_code": "FR", "origin": "POZ", "dest": dest, "origin_name": "Poznań",
            "dest_name": dest, "out_dep": f"{out}T07:00", "out_arr": f"{out}T10:00", "out_no": "FR1",
            "back_dep": f"{back}T18:00", "back_arr": f"{back}T21:00", "back_no": "FR2",
            "fare_total": fare_total, "fare_pp": fare_total / 2, "prev_total": None}


class FakeRyanair:
    name = "Ryanair"

    def __init__(self, failing=()):
        self.failing = set(failing)

    def routes(self, origin):
        return {d: {} for d in DESTS} if origin == "POZ" else {}

    def round_trips(self, origin, dest, *a):
        if dest in self.failing:
            raise RuntimeError("HTTP 429")
        return [combo(dest, day, 300 + 20 * day) for day in (6, 9, 13, 16, 20, 23)]


def stay(price):
    return {"id": "h1", "name": "Hotel Test", "kind": "Hotel 3★", "type": "Hotel", "stars": 3, "apartment": False,
            "hostel_like": False, "rating": 8.6, "rating_source": "trivago", "reviews": 900, "distance_km": 1.2,
            "lat": 0, "lon": 0, "image": None, "amenities": [], "price_total": price, "price_night": price // 3,
            "provider": "Booking.com", "trivago_url": "https://www.trivago.pl/pl/lm/hotel-test?search=dr-1;rc-1-2"}


class FakeTrivago:
    calls = 0

    def __init__(self, fail=False):
        self.fail = fail

    def offers(self, lat, lon, ci, co):
        if self.fail:
            raise RuntimeError("trivago: all searches failed (HTTP 403)")
        return [stay(900), stay(1100)]


class FakeWizz:
    name = "Wizz Air"

    def __init__(self, down=False):
        self.down = down

    def routes(self, origin):
        if self.down:
            raise RuntimeError("Wizz Air niedostępny: HTTP 429")
        return {"BUD": {}} if origin == "WRO" else {}

    def round_trips(self, origin, dest, *a):
        c = combo(dest, 8, 180)
        return [{**c, "origin": origin, "carrier": "Wizz Air", "carrier_code": "W6", "arr_estimated": True,
                 "two_seats_confirmed": False}]


def run(tmp_path, **kw):
    s = Settings(origins=("POZ", "WRO"), max_hotel_searches=kw.pop("max_hotel_searches", 4))
    kw.setdefault("wizz", FakeWizz())
    return search(tmp_path / "site", tmp_path / "state", s, rate=(4.0, "kurs testowy"), now=NOW,
                  weather_fn=lambda *a: {"kind": "forecast", "t_max": 20, "text": "x", "icon": "sun"}, **kw)


def source_status(payload, name):
    return next(x["status"] for x in payload["stats"]["sources"] if x["name"] == name)


def test_published_totals_are_flights_plus_bags_plus_stay(tmp_path):
    payload = run(tmp_path, ryanair=FakeRyanair(), trivago=FakeTrivago())
    published = json.loads((tmp_path / "site/data/deals.json").read_text())
    assert published["date"] == "2026-09-25" and not published["sample"]
    assert len(published["deals"]) == 4                     # one per city, 4 hotel searches
    for d in published["deals"]:
        for bag, info in d["flight"]["bags"].items():
            assert d["totals"][bag] == d["flight"]["fare_total"] + info["total"] + d["stay"]["price_total"]
        assert d["stay"]["price_total"] == 900              # the cheaper eligible stay is chosen
        assert (tmp_path / "site" / d["share_path"]).exists()
    assert (tmp_path / "state/fares.json").exists()
    assert source_status(payload, "Open-Meteo") == "4/4 ofert"


def _write_previous(tmp_path):
    (tmp_path / "site/data").mkdir(parents=True)
    (tmp_path / "site/data/deals.json").write_text('{"date": "2026-09-24", "marker": "yesterday"}')


def test_mostly_failing_ryanair_publishes_nothing(tmp_path):
    _write_previous(tmp_path)
    with pytest.raises(RuntimeError, match="nie nadpisuję"):
        run(tmp_path, ryanair=FakeRyanair(failing=("BCN", "BGY", "LIS")), trivago=FakeTrivago())
    assert json.loads((tmp_path / "site/data/deals.json").read_text())["marker"] == "yesterday"


def test_failing_trivago_publishes_nothing(tmp_path):
    _write_previous(tmp_path)
    with pytest.raises(RuntimeError, match="nie nadpisuję"):
        run(tmp_path, ryanair=FakeRyanair(), trivago=FakeTrivago(fail=True))
    assert json.loads((tmp_path / "site/data/deals.json").read_text())["marker"] == "yesterday"


def test_one_failing_route_is_tolerated_and_reported(tmp_path):
    payload = run(tmp_path, ryanair=FakeRyanair(failing=("LIS",)), trivago=FakeTrivago())
    assert {d["city"]["key"] for d in payload["deals"] if d["flight"]["carrier_code"] == "FR"} == {"barcelona", "mediolan", "rzym"}
    assert any("POZ-LIS" in e for e in payload["stats"]["errors"])


def test_wizz_deals_are_added_with_their_own_links_and_flags(tmp_path):
    payload = run(tmp_path, ryanair=FakeRyanair(), trivago=FakeTrivago(), max_hotel_searches=5)
    wizz = [d for d in payload["deals"] if d["flight"]["carrier_code"] == "W6"]
    assert len(wizz) == 1
    d = wizz[0]
    assert d["id"] == "wro-bud-20261008-20261011-w6"                     # never collides with a Ryanair id
    assert d["flight"]["book_url"] == "https://www.wizzair.com/pl-pl/booking/select-flight/WRO/BUD/2026-10-08/2026-10-11/2/0/0/null"
    assert d["flight"]["two_seats_confirmed"] is False and d["flight"]["out"]["arr_estimated"] is True
    assert d["trip"]["on_ground_estimated"] is True
    assert "Wizz Air" in d["flight"]["bags"]["cabin10"]["basis"]           # the Wizz fee table, not Ryanair's
    assert source_status(payload, "Wizz Air").startswith("1 kombinacji")


def test_wizz_outage_does_not_stop_ryanair_deals(tmp_path):
    payload = run(tmp_path, ryanair=FakeRyanair(), trivago=FakeTrivago(), wizz=FakeWizz(down=True))
    assert payload["deals"] and all(d["flight"]["carrier_code"] == "FR" for d in payload["deals"])
    assert source_status(payload, "Wizz Air").startswith("niedostępny")
