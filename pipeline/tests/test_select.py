from datetime import date

from wypad.config import Settings
from wypad.destinations import city_for_airport
from wypad.select import build_candidates, shortlist, typical_fares

TODAY = date(2026, 9, 25)
CITIES = {i: city_for_airport(i) for i in ("BCN", "BGY", "LIS", "CIA")}


def combo(dest, out, back, fare, origin="POZ", arr="10:00", dep="18:00"):
    return {"origin": origin, "dest": dest, "carrier": "Ryanair", "out_dep": f"{out}T07:00", "out_arr": f"{out}T{arr}",
            "back_dep": f"{back}T{dep}", "back_arr": f"{back}T21:00", "fare_pp": fare, "fare_total": 2 * fare, "prev_total": None}


def bags(c):
    return {"small": {"total": 0}, "cabin10": {"total": 200}, "checked20": {"total": 280}}


def test_typical_fare_needs_five_samples():
    combos = [combo("BCN", "2026-10-0%d" % d, "2026-10-1%d" % d, 100 * d) for d in range(1, 6)] + [combo("LIS", "2026-10-02", "2026-10-05", 50)]
    assert typical_fares(combos) == {"POZ-BCN": 300.0}


def test_candidates_respect_horizon_nights_and_whitelist():
    s = Settings()
    combos = [
        combo("BCN", "2026-10-16", "2026-10-19", 300),      # ok: 3 nights
        combo("BCN", "2026-10-16", "2026-10-17", 100),      # 1 night → out
        combo("BCN", "2026-12-01", "2026-12-04", 100),      # beyond 8 weeks → out
        combo("BCN", "2026-09-25", "2026-09-28", 100),      # departs today → out (min lead 1 day)
        combo("AMM", "2026-10-16", "2026-10-19", 100),      # Amman: not a European city break → out
    ]
    cands = build_candidates(combos, {**CITIES, "AMM": None}, {}, bags, s, TODAY)
    assert [(c["dest"], c["nights"]) for c in cands] == [("BCN", 3)]
    c = cands[0]
    assert c["est_total"] == 2 * 300 + 200 + 3 * CITIES["BCN"]["hotel_night"]
    assert c["check_in"] == date(2026, 10, 16) and c["check_out"] == date(2026, 10, 19)


def test_shortlist_takes_one_trip_per_city_before_second_dates():
    s = Settings(max_hotel_searches=3, max_candidates_per_city=2)
    combos = [combo("BGY", "2026-10-06", "2026-10-09", 70), combo("BGY", "2026-10-20", "2026-10-23", 71),
              combo("CIA", "2026-10-13", "2026-10-16", 140), combo("BCN", "2026-10-16", "2026-10-19", 200)]
    picked = shortlist(build_candidates(combos, CITIES, {}, bags, s, TODAY), s)
    assert sorted(c["dest"] for c in picked) == ["BCN", "BGY", "CIA"]   # 3 cities before a 2nd Bergamo date


def test_shortlist_is_diverse_and_skips_overlapping_dates():
    s = Settings(max_hotel_searches=4, max_candidates_per_city=2)
    combos = [
        combo("BGY", "2026-10-06", "2026-10-09", 70),
        combo("BGY", "2026-10-07", "2026-10-10", 71),   # overlaps the first BGY → skipped
        combo("BGY", "2026-10-20", "2026-10-23", 72),   # second BGY, no overlap → kept
        combo("BGY", "2026-11-03", "2026-11-06", 73),   # third BGY → over the per-city cap
        combo("CIA", "2026-10-13", "2026-10-16", 90),
        combo("BCN", "2026-10-16", "2026-10-19", 150),
    ]
    picked = shortlist(build_candidates(combos, CITIES, {}, bags, s, TODAY), s)
    assert len(picked) == 4
    bgy = sorted(c["out_dep"][:10] for c in picked if c["dest"] == "BGY")
    assert bgy == ["2026-10-06", "2026-10-20"]
    assert {c["dest"] for c in picked} == {"BGY", "CIA", "BCN"}
