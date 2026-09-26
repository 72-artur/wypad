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
