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


class DatedHttp(FakeHttp):
    """Answers every requested day with one priced flight — like the real timetable, but for any window."""

    def post_json(self, url, body, headers=None, **kw):
        from datetime import timedelta
        self.posts.append((body, headers or {}))
        legs = []
        for leg in body["flightList"]:
            d, to, flights = date.fromisoformat(leg["from"]), date.fromisoformat(leg["to"]), []
            while d <= to:
                flights.append({"priceType": "price", "price": {"amount": 100.0, "currencyCode": "PLN"},
                                "departureDates": [f"{d}T10:00:00"]})
                d += timedelta(days=1)
            legs.append(flights)
        return {"outboundFlights": legs[0], "returnFlights": legs[1]}


def test_windows_respect_the_api_limit_and_leave_no_gaps():
    from wypad.sources.wizzair import MAX_SPAN_DAYS
    http = DatedHttp()
    out_from, out_to, back_to = date(2026, 9, 27), date(2026, 11, 21), date(2026, 11, 26)
    combos = WizzAir(http).round_trips("WRO", "BCN", out_from, out_to, back_to, 1, 5)
    for body, _ in http.posts:
        for leg in body["flightList"]:
            assert (date.fromisoformat(leg["to"]) - date.fromisoformat(leg["from"])).days <= MAX_SPAN_DAYS
    got = {(c["out_dep"][:10], c["back_dep"][:10]) for c in combos}
    from datetime import timedelta
    expected = {(str(out_from + timedelta(days=i)), str(out_from + timedelta(days=i + n)))
                for i in range((out_to - out_from).days + 1) for n in range(1, 6)
                if out_from + timedelta(days=i + n) <= back_to}
    assert got == expected                         # every departure day × every stay length, none lost at window edges
    assert all(c["fare_total"] == 400.0 and c["fare_pp"] == 200.0 for c in combos)


def test_later_calls_echo_the_anti_forgery_token():
    http = DatedHttp()
    http.s.cookies.set("RequestVerificationToken", "tok-1", domain=".wizzair.com")
    WizzAir(http).round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 10, 10), date(2026, 10, 15), 2, 4)
    assert http.posts and all(h.get("X-RequestVerificationToken") == "tok-1" for _, h in http.posts)


def test_real_fixture_pairs_nights_and_prices_for_two():
    combos = WizzAir(FakeHttp()).round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 10, 20), date(2026, 10, 26), 2, 4)
    assert combos
    for c in combos:
        nights = (date.fromisoformat(c["back_dep"][:10]) - date.fromisoformat(c["out_dep"][:10])).days
        assert 2 <= nights <= 4
        assert c["fare_total"] == 2 * c["fare_pp"] and c["carrier_code"] == "W6"
        assert c["arr_estimated"] and c["two_seats_confirmed"] is False and c["out_no"] is None


def test_days_with_several_flights_or_other_currency_are_skipped():
    flights = [
        {"priceType": "price", "price": {"amount": 99.0, "currencyCode": "PLN"}, "departureDates": ["2026-10-01T06:00:00", "2026-10-01T18:00:00"]},
        {"priceType": "price", "price": {"amount": 25.0, "currencyCode": "EUR"}, "departureDates": ["2026-10-02T06:00:00"]},
        {"priceType": "checkPrice", "price": {"amount": 0.0, "currencyCode": "PLN"}, "departureDates": ["2026-10-03T06:00:00"]},
        {"priceType": "price", "price": {"amount": 149.0, "currencyCode": "PLN"}, "departureDates": ["2026-10-04T06:00:00"]},
    ]
    assert _days(flights) == {date(2026, 10, 4): ("2026-10-04T06:00", 149.0)}


def test_breaker_stops_after_three_failed_routes_and_budget_stops_everything():
    class Down(FakeHttp):
        def post_json(self, url, body, headers=None, **kw):
            self.posts.append(body)
            raise RuntimeError("HTTP 503")

    import pytest
    http = Down()
    w = WizzAir(http)
    for _ in range(5):
        with pytest.raises(RuntimeError):
            w.round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 10, 10), date(2026, 10, 15), 2, 4)
    assert len(http.posts) == 3                    # three routes tried, the rest skipped without a call

    ticks = iter([0, 1000, 1000])                  # budget of 480 s already used up at the first route
    w2 = WizzAir(DatedHttp(), clock=lambda: next(ticks))
    with pytest.raises(RuntimeError, match="limit czasu"):
        w2.round_trips("WRO", "BCN", date(2026, 9, 27), date(2026, 10, 10), date(2026, 10, 15), 2, 4)


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


def test_time_zone_comes_from_our_city_list_not_only_from_wizz():
    class NoCountry(FakeHttp):
        def get_json(self, url, params=None, **kw):
            data = super().get_json(url, params, **kw)
            for c in data["cities"]:
                c.pop("countryCode", None)           # Wizz omits the country → we still know BCN is in Spain
            return data

    w = WizzAir(NoCountry())
    assert w._geo("BCN")["cc"] == "ES" and w._geo("WRO")["cc"] == "PL"


def test_return_arrival_uses_the_home_time_zone():
    # London → Wrocław: 10:00 in London is 11:00 in Poland, + ~2 h 10 min → about 13:10 Polish time
    arr = estimate_arrival("2026-10-08T10:00", LTN, WRO)
    assert "13:00" <= arr[11:] <= "13:20"
