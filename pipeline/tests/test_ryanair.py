import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from wypad.sources.ryanair import Ryanair, booking_url

FIX = json.loads((Path(__file__).parent / "fixtures" / "ryanair_roundtrip_POZ_ARN_2adults.json").read_text())


class FakeHttp:
    def __init__(self, payload):
        self.payload, self.calls = payload, []

    def get_json(self, url, params=None, **kw):
        self.calls.append((url, params))
        return self.payload


def test_round_trips_are_normalized_from_a_real_response():
    http = FakeHttp(FIX)
    combos = Ryanair(http).round_trips("POZ", "ARN", date(2026, 9, 26), date(2026, 11, 20), date(2026, 11, 24), 2, 4)
    assert len(combos) == 3
    c = combos[2]
    assert (c["origin"], c["dest"], c["carrier"]) == ("POZ", "ARN", "Ryanair")
    assert c["out_dep"] == "2026-10-01T10:15" and c["out_arr"] == "2026-10-01T11:50" and c["out_no"] == "FR7679"
    assert c["back_dep"] == "2026-10-03T15:00"
    # adultPaxCount=2 → the summary price is the total for 2 adults (130.00 out + 150.88 back)
    assert c["fare_total"] == 280.88 and c["fare_pp"] == 140.44
    url, params = http.calls[0]
    assert url.endswith("/farfnd/v4/roundTripFares")
    assert params["arrivalAirportIataCode"] == "ARN" and params["currency"] == "PLN" and params["durationTo"] == 4
    assert params["adultPaxCount"] == 2


def test_foreign_currency_and_broken_rows_are_dropped():
    bad = json.loads(json.dumps(FIX))
    bad["fares"][0]["summary"]["price"]["currencyCode"] = "EUR"
    del bad["fares"][1]["inbound"]
    assert len(Ryanair(FakeHttp(bad)).round_trips("POZ", "ARN", date(2026, 9, 26), date(2026, 11, 20), date(2026, 11, 24), 2, 4)) == 1


def test_previous_price_is_summed_over_both_legs():
    fx = json.loads(json.dumps(FIX))
    fx["fares"][0]["outbound"]["previousPrice"] = {"value": 99.0}
    c = Ryanair(FakeHttp(fx)).round_trips("POZ", "ARN", date(2026, 9, 26), date(2026, 11, 20), date(2026, 11, 24), 2, 4)[0]
    assert c["prev_total"] == 99.0 + fx["fares"][0]["inbound"]["price"]["value"]


def test_booking_url_prefills_route_dates_and_two_adults():
    q = parse_qs(urlparse(booking_url("POZ", "BCN", "2026-10-16", "2026-10-19")).query)
    assert q["originIata"] == ["POZ"] and q["destinationIata"] == ["BCN"]
    assert q["dateOut"] == ["2026-10-16"] and q["dateIn"] == ["2026-10-19"]
    assert q["adults"] == ["2"] and q["isReturn"] == ["true"]
