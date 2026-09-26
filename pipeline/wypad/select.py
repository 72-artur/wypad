"""Turns raw flight combinations into ranked trip candidates and picks a diverse shortlist
for the (expensive) accommodation search."""
from __future__ import annotations

import statistics
from datetime import date

from .config import Settings
from .scoring import deal_score, discount_vs_typical
from .trip import hours_on_ground, stay_dates


def typical_fares(combos: list[dict]) -> dict[str, float]:
    """Median round-trip fare per person for each route across all dates in the search window.
    "This date is 40% cheaper than a typical date on this route" is the promo signal on day one;
    later runs blend in the stored history (see history.py)."""
    by_route: dict[str, list[float]] = {}
    for c in combos:
        by_route.setdefault(f"{c['origin']}-{c['dest']}", []).append(c["fare_pp"])
    return {r: float(statistics.median(v)) for r, v in by_route.items() if len(v) >= 5}


def build_candidates(combos: list[dict], cities: dict[str, dict], typical: dict[str, float],
                     bag_estimate, s: Settings, today: date) -> list[dict]:
    out = []
    for c in combos:
        city = cities.get(c["dest"])
        if not city:
            continue
        out_date = date.fromisoformat(c["out_dep"][:10])
        lead = (out_date - today).days
        if lead < s.min_lead_days or lead > s.horizon_days:
            continue
        check_in, check_out = stay_dates(c["out_arr"], c["back_dep"])
        nights = (check_out - check_in).days
        if nights not in s.nights:
            continue
        bags = bag_estimate(c)
        est_total = c["fare_total"] + bags[s.default_bag]["total"] + city["hotel_night"] * nights
        on_ground = hours_on_ground(c["out_arr"], c["back_dep"])
        typ = typical.get(f"{c['origin']}-{c['dest']}")
        disc = discount_vs_typical(c["fare_pp"], typ)
        out.append({**c, "city": city, "check_in": check_in, "check_out": check_out, "nights": nights,
                    "lead_days": lead, "on_ground_h": on_ground, "discount_pct": disc, "bags": bags,
                    "typical_pp": round(typ) if typ else None,
                    "est_total": round(est_total),
                    "pre_score": deal_score(total_pln=est_total, nights=nights, discount_pct=disc, rating=None,
                                            distance_km=None, on_ground_h=on_ground, origin=c["origin"])})
    return out


def _overlaps(a: dict, b: dict) -> bool:
    return a["check_in"] < b["check_out"] and b["check_in"] < a["check_out"]


def shortlist(cands: list[dict], s: Settings) -> list[dict]:
    """Best pre-scored candidates for the hotel search. First one trip per city (so the list is varied),
    then a second, non-overlapping date for the strongest cities; trips far above the default budget
    only fill leftover slots."""
    ranked = sorted(cands, key=lambda c: (-c["pre_score"], c["est_total"]))
    affordable = [c for c in ranked if c["est_total"] <= s.budget_pln * 1.3]
    picked: list[dict] = []

    def take(pool: list[dict], per_city: int) -> None:
        for c in pool:
            if len(picked) >= s.max_hotel_searches:
                return
            same_city = [p for p in picked if p["city"]["key"] == c["city"]["key"]]
            if c in picked or len(same_city) >= per_city or any(_overlaps(c, p) for p in same_city):
                continue
            picked.append(c)

    take(affordable, 1)
    take(affordable, s.max_candidates_per_city)
    take(ranked, s.max_candidates_per_city)
    return picked
