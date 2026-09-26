from datetime import date

from wypad.trip import hours_on_ground, is_weekend_trip, stay_dates, trip_labels


def test_stay_matches_flight_dates_for_daytime_flights():
    assert stay_dates("2026-10-16T09:00", "2026-10-19T09:35") == (date(2026, 10, 16), date(2026, 10, 19))


def test_landing_after_midnight_books_the_previous_night():
    # Flight leaves Poznań 22:30 on 16.10 and lands 00:40 on 17.10 → the room is needed from 16.10.
    check_in, check_out = stay_dates("2026-10-17T00:40", "2026-10-20T10:00")
    assert check_in == date(2026, 10, 16)
    assert check_out == date(2026, 10, 20)


def test_departing_after_midnight_checks_out_the_evening_before():
    check_in, check_out = stay_dates("2026-10-16T12:00", "2026-10-20T01:15")
    assert (check_in, check_out) == (date(2026, 10, 16), date(2026, 10, 19))


def test_stay_never_has_zero_nights():
    check_in, check_out = stay_dates("2026-10-17T01:00", "2026-10-17T03:00")
    assert (check_out - check_in).days == 1


def test_hours_on_ground():
    assert hours_on_ground("2026-10-16T09:00", "2026-10-19T21:30") == 84.5


def test_weekend_trip_rules():
    assert is_weekend_trip(date(2026, 10, 16), date(2026, 10, 19))      # Fri → Mon
    assert is_weekend_trip(date(2026, 10, 15), date(2026, 10, 18))      # Thu → Sun
    assert is_weekend_trip(date(2026, 10, 17), date(2026, 10, 19))      # Sat → Mon
    assert not is_weekend_trip(date(2026, 10, 12), date(2026, 10, 15))  # Mon → Thu
    assert not is_weekend_trip(date(2026, 10, 16), date(2026, 10, 17))  # Fri → Sat: no Saturday night
    assert not is_weekend_trip(date(2026, 10, 14), date(2026, 10, 18))  # Wed departure needs days off


def test_labels():
    today = date(2026, 9, 25)
    labels = trip_labels(today=today, out_date=date(2026, 10, 9), back_date=date(2026, 10, 12), origin="POZ",
                         discount_pct=62, fare_pp=320, last_minute_days=21)
    assert labels == ["lastminute", "weekend", "promo", "poz"]
    labels = trip_labels(today=today, out_date=date(2026, 11, 4), back_date=date(2026, 11, 6), origin="WRO",
                         discount_pct=10, fare_pp=320, last_minute_days=21)
    assert labels == []


def test_promo_is_reserved_for_real_hits():
    kw = dict(today=date(2026, 9, 25), out_date=date(2026, 11, 4), back_date=date(2026, 11, 6), origin="WRO", last_minute_days=21)
    assert "promo" not in trip_labels(**kw, discount_pct=59, fare_pp=320)   # ~50% under median is normal for cheap dates
    assert "promo" in trip_labels(**kw, discount_pct=60, fare_pp=320)
    assert "promo" in trip_labels(**kw, discount_pct=None, fare_pp=160)     # very cheap even without price history
    assert "promo" not in trip_labels(**kw, discount_pct=None, fare_pp=161)
