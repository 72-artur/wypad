from wypad.scoring import deal_score, discount_vs_typical, typical_fare

BASE = dict(total_pln=2000, nights=3, discount_pct=20, rating=8.5, distance_km=1.0, on_ground_h=80, origin="POZ")


def test_cheaper_total_scores_higher():
    assert deal_score(**{**BASE, "total_pln": 1500}) > deal_score(**BASE) > deal_score(**{**BASE, "total_pln": 3000})


def test_poznan_is_favoured_over_other_airports():
    assert deal_score(**BASE) - deal_score(**{**BASE, "origin": "WRO"}) == 10


def test_better_hotel_and_more_time_on_ground_score_higher():
    assert deal_score(**{**BASE, "rating": 9.2}) > deal_score(**BASE)
    assert deal_score(**{**BASE, "distance_km": 0.3}) > deal_score(**BASE)
    assert deal_score(**{**BASE, "on_ground_h": 60}) < deal_score(**BASE)


def test_score_is_bounded():
    best = deal_score(total_pln=400, nights=4, discount_pct=90, rating=10, distance_km=0, on_ground_h=200, origin="POZ")
    worst = deal_score(total_pln=9000, nights=2, discount_pct=-50, rating=6, distance_km=9, on_ground_h=10, origin="WRO")
    assert best == 100 and worst == 0


def test_discount_and_typical_fare():
    assert discount_vs_typical(300, 500) == 40
    assert discount_vs_typical(300, None) is None
    assert typical_fare([100, 200, 300]) is None            # too few samples to call anything "typical"
    assert typical_fare([100, 200, 300, 400, 500, 0]) == 300
