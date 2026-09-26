"""Deal score 0–100 used for the default "Najlepsze okazje" order."""
from __future__ import annotations

import statistics


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def discount_vs_typical(fare_pp: float, typical_pp: float | None) -> int | None:
    """How much cheaper this round-trip fare is than the typical fare on the route (percent)."""
    if not typical_pp or typical_pp <= 0:
        return None
    return int(round(100 * (1 - fare_pp / typical_pp)))


def typical_fare(samples: list[float]) -> float | None:
    """Median of observed round-trip fares per person; needs a few samples to mean anything."""
    clean = [s for s in samples if s and s > 0]
    if len(clean) < 5:
        return None
    return float(statistics.median(clean))


def deal_score(*, total_pln: float, nights: int, discount_pct: int | None, rating: float | None,
               distance_km: float | None, on_ground_h: float, origin: str) -> int:
    """Weights: price per person-night 40, flight discount 20, stay quality 20, time on the ground 10,
    departure from Poznań 10 (Artur asked for POZ to be favoured in sorting)."""
    per_person_night = total_pln / (2 * max(nights, 1))
    s_price = _clamp((600 - per_person_night) / 400)          # 200 zł → 1.0, 600 zł → 0.0
    s_disc = 0.3 if discount_pct is None else _clamp((discount_pct - 20) / 50)   # 20% → 0, 70% → 1
    s_rating = 0.5 if rating is None else _clamp((rating - 7.5) / 1.7)
    s_dist = 0.5 if distance_km is None else _clamp(1 - distance_km / 3)
    s_stay = 0.6 * s_rating + 0.4 * s_dist
    s_time = _clamp((on_ground_h / (max(nights, 1) * 24) - 0.6) / 0.5)
    s_origin = 1.0 if origin == "POZ" else 0.0
    return int(round(40 * s_price + 20 * s_disc + 20 * s_stay + 10 * s_time + 10 * s_origin))
