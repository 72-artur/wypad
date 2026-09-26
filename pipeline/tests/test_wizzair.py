import json
from datetime import date
from pathlib import Path

from wypad.sources.wizzair import WizzAir, _days, booking_url, estimate_arrival, flight_minutes

FIX = json.loads((Path(__file__).parent / "fixtures" / "wizz_timetable_WRO_BCN.json").read_text())
WRO = {"lat": 51.1027, "lon": 16.8858, "cc": "PL", "name": "Wrocław"}
BCN = {"lat": 41.2971, "lon": 2.0785, "cc": "ES", "name": "Barcelona"}
LTN = {"lat": 51.8747, "lon": -0.3683, "cc": "GB", "name": "Londyn-Luton"}


class FakeHttp:
    def __init__(self):
        import requests
        self.posts = []
        self.s = requests.Session()

    def get_text(self, url, **kw):
        return 'xx apiUrl:"https://be.wizzair.com/29.18.0/Api" yy'

    def get_json(self, url, params=None, **kw):
        return {"cities": [
            {"iata": "WRO", "latitude": WRO["lat"], "longitude": WRO["lon"], "countryCode": "PL", "shortName": "Wrocław",
             "connections": [{"iata": "BCN", "isDirectFlight": True}, {"iata": "LON", "isDirectFlight": True},
                             {"iata": "KUT", "isDirectFlight": False}]},
            {"iata": "BCN", "latitude": BCN["lat"], "longitude": BCN["lon"], "countryCode": "ES", "shortName": "Barcelona"},
            {"iata": "LON", "isFakeStation": True, "shortName": "Londyn (wszystkie)"},
            {"iata": "KUT", "shortName": "Kutaisi"}]}

    def post_json(self, url, body, headers=None, **kw):
        self.posts.append(body)
        return FIX


def test_real_timetable_keeps_only_priced_single_flight_days():
    outs = _days(FIX["outboundFlights"])
    raw = FIX["outboundFlights"]
    priced = [f for f in raw if f["priceType"] == "price" and f["price"]["amount"] > 0 and len(f["departureDates"]) == 1]
    assert len(outs) == len(priced) and all(p > 0 for _, p in outs.values())
    assert all(f["priceType"] != "checkPrice" for f in priced)          # 'checkPrice' rows have price 0


def test_routes_skip_city_aliases_and_connections():
    w = WizzAir(FakeHttp())
    assert w.api() == "https://be.wizzair.com/29.18.0/Api"
    assert list(w.routes("WRO")) == ["BCN"]


def test_round_trips_pair_nights_price_for_two_and_split_windows():
    http = FakeHttp()
    combos = WizzAir(http).round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 11, 21), date(2026, 11, 26), 2, 4)
    assert len(http.posts) == 2                                         # 56 days → two 30-day windows
    for body in http.posts:
        out, back = body["flightList"]
        assert (date.fromisoformat(out["to"]) - date.fromisoformat(out["from"])).days <= 29
        assert (date.fromisoformat(back["to"]) - date.fromisoformat(back["from"])).days <= 35   # API rejects 41+ days
    assert combos
    for c in combos:
        nights = (date.fromisoformat(c["back_dep"][:10]) - date.fromisoformat(c["out_dep"][:10])).days
        assert 2 <= nights <= 4
        assert c["fare_total"] == 2 * c["fare_pp"] and c["carrier_code"] == "W6"
        assert c["arr_estimated"] and c["two_seats_confirmed"] is False and c["out_no"] is None


def test_arrival_estimate_uses_distance_and_time_zones():
    assert 150 <= flight_minutes(WRO["lat"], WRO["lon"], BCN["lat"], BCN["lon"]) <= 170    # real WRO–BCN ~2 h 40 min
    # Same zone: 10:00 + ~2 h 40 min → about 12:40 in Barcelona
    assert estimate_arrival("2026-10-08T10:00", WRO, BCN) in ("2026-10-08T12:35", "2026-10-08T12:40", "2026-10-08T12:45")
    # London is one hour behind Poland: 10:00 + ~2 h 10 min → about 11:10 local
    arr = estimate_arrival("2026-10-08T10:00", WRO, LTN)
    assert arr.startswith("2026-10-08T11:") and "11:00" <= arr[11:] <= "11:20"


def test_booking_link_format():
    assert booking_url("POZ", "BSL", "2026-11-06", "2026-11-09") == \
        "https://www.wizzair.com/pl-pl/booking/select-flight/POZ/BSL/2026-11-06/2026-11-09/2/0/0/null"


def test_failure_is_remembered_so_other_origins_fail_fast():
    import pytest

    class Down(FakeHttp):
        calls = 0

        def get_text(self, url, **kw):
            Down.calls += 1
            raise RuntimeError("HTTP 429")

    w = WizzAir(Down())
    for _ in range(3):
        with pytest.raises(RuntimeError, match="niedostępny"):
            w.routes("WRO")
    assert Down.calls == 1


def test_anti_forgery_token_is_echoed_after_the_first_call():
    import requests
    http = FakeHttp()
    http.s = requests.Session()
    w = WizzAir(http)
    assert "X-RequestVerificationToken" not in w._headers()          # first call: no cookie yet
    http.s.cookies.set("RequestVerificationToken", "abc123", domain=".wizzair.com")
    assert w._headers()["X-RequestVerificationToken"] == "abc123"   # later calls: 400 InvalidProtocol without it


def test_one_failed_window_keeps_the_other_windows_fares():
    import requests

    class HalfDown(FakeHttp):
        def post_json(self, url, body, headers=None, **kw):
            self.posts.append(body)
            if len(self.posts) == 2:
                raise RuntimeError("400 InvalidProtocol")
            return FIX

    http = HalfDown()
    http.s = requests.Session()
    combos = WizzAir(http).round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 11, 21), date(2026, 11, 26), 2, 4)
    assert combos and len(http.posts) == 2
