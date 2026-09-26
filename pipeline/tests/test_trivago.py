import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from wypad.sources.trivago import booking_city_url, booking_search_url, normalize, parse_pln, pick_stays

RAW = json.loads((Path(__file__).parent / "fixtures" / "trivago_milan_3n.json").read_text())["result"]["structuredContent"]["accommodations"]
MILAN = (45.4642, 9.19)
CI, CO = date(2026, 10, 20), date(2026, 10, 23)


def offers():
    return [o for a in RAW if (o := normalize(a, *MILAN, CI, CO))]


def test_price_parsing_handles_polish_formatting():
    assert parse_pln("1 333 zł") == 1333
    assert parse_pln("2 335 zł") == 2335
    assert parse_pln("1,965") == 1965
    assert parse_pln(None) is None


def test_real_response_is_normalized():
    os_ = offers()
    assert len(os_) == len(RAW)
    o = os_[0]
    assert o["price_total"] > 0 and o["price_night"] == round(o["price_total"] / 3)
    assert 0 <= o["distance_km"] < 20 and o["rating_source"] == "trivago"
    assert o["trivago_url"].startswith("https://www.trivago.pl/")


def test_pick_respects_rating_distance_and_excludes_hostels():
    os_ = offers()
    fake_hostel = {**os_[0], "name": "Central Youth Hostel", "hostel_like": True, "price_total": 1, "rating": 9.5, "distance_km": 0.1, "reviews": 999}
    far_cheap = {**os_[0], "name": "Far Away Inn", "hostel_like": False, "price_total": 2, "rating": 9.0, "distance_km": 12.0, "reviews": 999}
    low_rated = {**os_[0], "name": "Meh Hotel", "hostel_like": False, "price_total": 3, "rating": 7.4, "distance_km": 0.5, "reviews": 999}
    picks = pick_stays(os_ + [fake_hostel, far_cheap, low_rated], min_rating=8.0, max_km=3.0)
    assert picks, "the Milan fixture has eligible hotels"
    best = picks[0]
    assert best["name"] not in ("Central Youth Hostel", "Far Away Inn", "Meh Hotel")
    assert best["rating"] >= 8.0 and best["distance_km"] <= 5.0 and not best["hostel_like"]
    eligible = [o for o in os_ if o["rating"] and o["rating"] >= 8 and o["distance_km"] <= 3 and (o["reviews"] or 0) >= 100
                and ((o["stars"] or 0) >= 2 or o["apartment"]) and not o["hostel_like"]]
    if eligible:
        assert best["price_total"] == min(o["price_total"] for o in eligible)


def test_no_stay_when_nothing_meets_the_rating_floor():
    os_ = [{**o, "rating": 7.0} for o in offers()]
    assert pick_stays(os_, min_rating=8.0, max_km=3.0) == []


def test_booking_links_keep_dates_guests_and_filters():
    q = parse_qs(urlparse(booking_search_url("Hotel Varese Rzym", "2026-11-13", "2026-11-15")).query)
    assert q["ss"] == ["Hotel Varese Rzym"] and q["checkin"] == ["2026-11-13"] and q["checkout"] == ["2026-11-15"]
    assert q["group_adults"] == ["2"] and q["no_rooms"] == ["1"] and q["group_children"] == ["0"]
    city = booking_city_url("Rzym", "2026-11-13", "2026-11-15")
    assert "order=price" in city and "nflt=review_score%3D80%3Bht_id%3D204%3Bdistance%3D3000" in city


def test_backpacker_and_youth_hostels_are_flagged():
    from wypad.sources.trivago import HOSTEL_WORDS
    for name in ("The Full Moon Backpackers", "HelloBCN Youth Hostel", "Ostello Bello", "Jugendherberge Berlin", "Albergue Porto"):
        assert HOSTEL_WORDS.search(name), name
    for name in ("Hostal Madrazo", "Hotel Derby", "Estudiotel Alicante"):
        assert not HOSTEL_WORDS.search(name), name


def _raw(name, url_slug, stars=3, rating="8.8", reviews="1,234", lat=45.465, lon=9.19, price="1 500 zł"):
    return {"accommodation_id": url_slug, "accommodation_name": name, "hotel_rating": stars, "review_rating": rating,
            "review_count": reviews, "latitude": lat, "longitude": lon, "price_per_stay": price, "price_per_night": "500 zł",
            "currency": "PLN", "advertisers": "Booking.com",
            "accommodation_url": f"https://www.trivago.pl/pl/lm/{url_slug}?search=dr-20261020-20261023;rc-1-2"}


def test_hostel_is_detected_from_trivago_type_even_with_hotel_stars():
    # Real case from 2026-09-25: a hostel that trivago rates 4★ and whose name has no "hostel" in it.
    o = normalize(_raw("The Bristol Wing", "hostel-schronisko-the-bristol-wing", stars=4), *MILAN, CI, CO)
    assert o["hostel_like"] and o["kind"] == "Hostel" and o["stars"] is None
    assert pick_stays([o], min_rating=8.0, max_km=3.0) == []


def test_property_types_from_trivago_links():
    cases = {
        "cały-dom-apartament-apartment-secession-style-sofia-miasto": ("Apartament", True),
        "aparthotel-estudiotel-alicante": ("Aparthotel", True),
        "hotel-malcom-and-barret-walencja": ("Hotel 3★", False),
    }
    for slug, (kind, apartment) in cases.items():
        o = normalize(_raw("X", slug), *MILAN, CI, CO)
        assert (o["kind"], o["apartment"]) == (kind, apartment), slug
    # No type prefix (trivago omits it when the name already says "hotel")
    assert normalize(_raw("Clayton Hotel Bristol City", "clayton-hotel-bristol-city", stars=4), *MILAN, CI, CO)["kind"] == "Hotel 4★"
    assert normalize(_raw("YHA Manchester", "yha-manchester", stars=0), *MILAN, CI, CO)["hostel_like"]


def test_whole_apartment_without_stars_is_eligible():
    o = normalize(_raw("Apartment Secession Style", "cały-dom-apartament-apartment-secession-style", stars=0), *MILAN, CI, CO)
    assert pick_stays([o], min_rating=8.0, max_km=3.0) == [o]


def test_trivago_link_carries_dates_and_two_adults():
    for o in offers():
        assert "dr-20261020-20261023" in o["trivago_url"] and "rc-1-2" in o["trivago_url"]


class _FailingTrivago:
    def __init__(self, fail_first_n):
        self.n, self.calls = fail_first_n, 0

    def __call__(self, args):
        self.calls += 1
        if self.calls <= self.n:
            raise RuntimeError("HTTP 403")
        return RAW[:2]


def test_offers_survive_one_failed_variant_but_raise_when_all_fail():
    import pytest
    from wypad.sources.trivago import Trivago
    t = Trivago()
    t._search = _FailingTrivago(fail_first_n=2)
    assert len(t.offers(*MILAN, CI, CO)) == 2
    t._search = _FailingTrivago(fail_first_n=3)
    with pytest.raises(RuntimeError, match="all searches failed"):
        t.offers(*MILAN, CI, CO)
