"""Pure date/time logic for a round trip. No I/O, fully unit-tested."""
from __future__ import annotations

from datetime import date, datetime, timedelta

LATE_ARRIVAL_HOUR = 5  # landing before 05:00 → the hotel night must start the day before


def parse_local(ts: str) -> datetime:
    """Parse '2026-10-16T06:10' or '2026-10-16T06:10:00.000' (airport local time, naive)."""
    return datetime.fromisoformat(ts[:19] if len(ts) >= 19 else ts[:16])


def stay_dates(out_arrival: str, back_departure: str) -> tuple[date, date]:
    """Hotel check-in/check-out for 2 adults, derived from the flight times.

    - Landing after midnight but before 05:00 needs a room from the previous evening.
    - Departing after midnight but before 05:00 means you leave the hotel the evening before.
    """
    arr = parse_local(out_arrival)
    dep = parse_local(back_departure)
    check_in = arr.date() - timedelta(days=1) if arr.hour < LATE_ARRIVAL_HOUR else arr.date()
    check_out = dep.date() - timedelta(days=1) if dep.hour < LATE_ARRIVAL_HOUR else dep.date()
    if check_out <= check_in:
        check_out = check_in + timedelta(days=1)
    return check_in, check_out


def hours_on_ground(out_arrival: str, back_departure: str) -> float:
    """Hours between landing at the destination and taking off home (both local times)."""
    delta = parse_local(back_departure) - parse_local(out_arrival)
    return round(delta.total_seconds() / 3600, 1)


def is_weekend_trip(out_date: date, back_date: date) -> bool:
    """Leave Thu/Fri/Sat, return Sun/Mon, and stay over the Saturday night."""
    if out_date.weekday() not in (3, 4, 5) or back_date.weekday() not in (6, 0):
        return False
    saturday = out_date + timedelta(days=(5 - out_date.weekday()) % 7)
    return out_date <= saturday < back_date


def days_until(today: date, d: date) -> int:
    return (d - today).days


def trip_labels(*, today: date, out_date: date, back_date: date, origin: str,
                discount_pct: int | None, fare_pp: float, last_minute_days: int) -> list[str]:
    labels: list[str] = []
    if 0 <= days_until(today, out_date) <= last_minute_days:
        labels.append("lastminute")
    if is_weekend_trip(out_date, back_date):
        labels.append("weekend")
    # The cheapest dates of any route sit ~50% under its median, so "promo" is reserved for real hits.
    if (discount_pct or 0) >= 60 or fare_pp <= 160:
        labels.append("promo")
    if origin == "POZ":
        labels.append("poz")
    return labels
