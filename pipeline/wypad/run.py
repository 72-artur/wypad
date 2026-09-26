"""Daily search: flights → candidates → stays → deals → static site files."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import bags, history
from .config import BAG_OPTIONS, ORIGINS, Settings
from .destinations import city_for_airport
from .http import Http
from .links import google_flights_url
from .output import publish
from .scoring import deal_score
from .select import build_candidates, shortlist, typical_fares
from .sources.ryanair import Ryanair, booking_url as ryanair_booking_url
from .sources.trivago import Trivago, booking_city_url, booking_search_url, pick_stays
from .trip import is_weekend_trip, trip_labels
from .weather import trip_weather

log = logging.getLogger(__name__)
WARSAW = ZoneInfo("Europe/Warsaw")

STAY_NOTE = ("Cena łączna za pobyt według trivago ({provider}), sprawdzona {when}. "
             "Ewentualną opłatę miejscową i ostateczną kwotę zobaczysz na stronie rezerwacji.")


def collect_flights(ry: Ryanair, s: Settings, today: date) -> tuple[list[dict], list[str]]:
    combos, errors = [], []
    out_from = today + timedelta(days=s.min_lead_days)
    out_to = today + timedelta(days=s.horizon_days)
    back_to = out_to + timedelta(days=max(s.nights) + 1)
    for origin in s.origins:
        try:
            routes = ry.routes(origin)
        except Exception as e:  # noqa: BLE001
            errors.append(f"Ryanair trasy {origin}: {e}")
            continue
        for dest in sorted(d for d in routes if city_for_airport(d)):
            try:
                # +1 night of slack: a flight landing after midnight shifts the hotel night (see trip.stay_dates).
                combos += ry.round_trips(origin, dest, out_from, out_to, back_to, min(s.nights) - 1, max(s.nights) + 1)
            except Exception as e:  # noqa: BLE001
                errors.append(f"Ryanair {origin}-{dest}: {e}")
    return combos, errors


def leg(c: dict, which: str) -> dict:
    o = which == "out"
    frm, to = (c["origin"], c["dest"]) if o else (c["dest"], c["origin"])
    return {
        "from": frm, "to": to,
        "from_name": c["origin_name"] if o else c["dest_name"],
        "to_name": c["dest_name"] if o else c["origin_name"],
        "from_city": ORIGINS[c["origin"]]["city"] if o else None,
        "dep": c[f"{which}_dep"], "arr": c[f"{which}_arr"], "no": _flight_no(c.get(f"{which}_no")),
        "seats_left": None,
    }


def _flight_no(no: str | None) -> str | None:
    return f"{no[:2]} {no[2:]}" if no and len(no) > 2 and no[:2].isalpha() else no


def assemble(c: dict, stays: list[dict], weather: dict | None, s: Settings, today: date, checked_at: str) -> dict:
    city = c["city"]
    out_date, back_date = c["out_dep"][:10], c["back_dep"][:10]
    best, alts = stays[0], stays[1:]
    ci, co = c["check_in"].isoformat(), c["check_out"].isoformat()
    fare_total = round(c["fare_total"])
    totals = {k: round(fare_total + v["total"] + best["price_total"]) for k, v in c["bags"].items()}
    stay_block = lambda o: {  # noqa: E731
        "name": o["name"], "kind": o["kind"], "stars": o["stars"], "rating": o["rating"], "rating_source": o["rating_source"],
        "reviews": o["reviews"], "distance_km": o["distance_km"], "image": o["image"], "amenities": o["amenities"],
        "price_total": o["price_total"], "price_night": o["price_night"], "provider": o["provider"],
        "book_url": o["trivago_url"], "booking_url": booking_search_url(f"{o['name']} {city['name']}", ci, co),
    }
    return {
        "id": f"{c['origin']}-{c['dest']}-{out_date.replace('-', '')}-{back_date.replace('-', '')}".lower(),
        "score": deal_score(total_pln=totals[s.default_bag], nights=c["nights"], discount_pct=c["discount_pct"],
                            rating=best["rating"], distance_km=best["distance_km"], on_ground_h=c["on_ground_h"],
                            origin=c["origin"]),
        "labels": trip_labels(today=today, out_date=date.fromisoformat(out_date), back_date=date.fromisoformat(back_date),
                              origin=c["origin"], discount_pct=c["discount_pct"], fare_pp=c["fare_pp"],
                              last_minute_days=s.last_minute_days),
        "price_drop": 0,
        "city": {k: city[k] for k in ("key", "name", "country", "cc", "accent", "via", "tagline")},
        "trip": {"out_date": out_date, "back_date": back_date, "nights": c["nights"], "on_ground_h": c["on_ground_h"],
                 "weekend": is_weekend_trip(date.fromisoformat(out_date), date.fromisoformat(back_date)),
                 "days_to_departure": c["lead_days"]},
        "flight": {
            "carrier": c["carrier"], "carrier_code": c["carrier_code"],
            "out": leg(c, "out"), "back": leg(c, "back"),
            "fare_pp": round(c["fare_pp"]), "fare_total": fare_total,
            "discount_pct": c["discount_pct"] if (c["discount_pct"] or 0) > 0 else None,
            "typical_pp": c.get("typical_pp"),
            "bags": c["bags"],
            "book_url": ryanair_booking_url(c["origin"], c["dest"], out_date, back_date),
            "compare_url": google_flights_url(c["origin"], c["dest"], out_date, back_date),
        },
        "stay": {**stay_block(best), "check_in": ci, "check_out": co, "nights": c["nights"], "adults": 2,
                 "source": "trivago", "booking_city_url": booking_city_url(city["name"], ci, co),
                 "taxes_note": STAY_NOTE.format(provider=best["provider"] or "najlepsza oferta", when=checked_at_label(checked_at)),
                 "alternatives": [stay_block(a) for a in alts]},
        "totals": totals,
        "transfer": city["transfer"],
        "weather": weather,
        "checked_at": checked_at,
    }


def checked_at_label(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d} o {d.hour:02d}:{d.minute:02d}"


def search(site_dir: Path, state_dir: Path, s: Settings | None = None) -> dict:
    s = s or Settings()
    t0 = time.monotonic()
    now = datetime.now(WARSAW)
    today = now.date()
    http = Http(delay_s=s.request_delay_s)
    ry = Ryanair(http)

    combos, errors = collect_flights(ry, s, today)
    log.info("flights: %d combinations, %d errors", len(combos), len(errors))
    if not combos:
        raise RuntimeError("Brak danych o lotach — nie nadpisuję wczorajszych okazji. " + "; ".join(errors[:5]))

    stored = history.load_fares(state_dir)
    today_typical = typical_fares(combos)
    typical = history.typical_with_history(today_typical, stored, today)
    cities = {c["dest"]: city_for_airport(c["dest"]) for c in combos}
    rate, rate_label = bags.eur_pln(http)
    cands = build_candidates(combos, cities, typical, bags.estimator(rate, rate_label), s, today)
    picked = shortlist(cands, s)
    log.info("candidates: %d, shortlisted for hotels: %d", len(cands), len(picked))

    tv = Trivago()
    deals, stay_errors = [], 0
    for c in picked:
        try:
            offers = tv.offers(c["city"]["lat"], c["city"]["lon"], c["check_in"], c["check_out"])
        except Exception as e:  # noqa: BLE001
            stay_errors += 1
            errors.append(f"trivago {c['city']['name']}: {e}")
            continue
        stays = pick_stays(offers, min_rating=s.min_rating, max_km=s.max_distance_km)
        if not stays:
            log.info("no eligible stay for %s %s", c["city"]["name"], c["check_in"])
            continue
        weather = trip_weather(c["city"]["lat"], c["city"]["lon"], c["check_in"], c["check_out"], today)
        deals.append(assemble(c, stays, weather, s, today, now.isoformat(timespec="minutes")))

    if not deals:
        raise RuntimeError("Nie udało się dobrać noclegów do żadnego lotu — nie nadpisuję wczorajszych okazji. "
                           + "; ".join(errors[:5]))

    history.mark_changes(deals, history.previous_payload(site_dir, today), s.default_bag)
    deals.sort(key=lambda d: (-d["score"], d["totals"][s.default_bag]))
    deals = deals[: s.max_deals]

    payload = {
        "schema": 1, "sample": False, "generated_at": now.isoformat(timespec="minutes"), "date": today.isoformat(),
        "currency": "PLN",
        "defaults": {"budget": s.budget_pln, "bag": s.default_bag, "origins": list(s.origins), "nights": list(s.nights),
                     "horizon_days": s.horizon_days, "last_minute_days": s.last_minute_days},
        "origins": {k: {"city": v["city"], "city_gen": v["city_gen"], "drive": v["drive"]} for k, v in ORIGINS.items()},
        "bag_options": BAG_OPTIONS,
        "stats": {
            "flight_options": len(combos), "candidates": len(cands), "hotel_searches": len(picked),
            "http_calls": http.calls + tv.calls, "duration_s": round(time.monotonic() - t0),
            "errors": errors[:20],
            "sources": [
                {"name": "Ryanair", "role": "Ceny i godziny lotów dla 2 dorosłych (wyszukiwarka ryanair.com)", "status": f"{len(combos)} kombinacji"},
                {"name": "Cennik Ryanair + NBP", "role": "Szacunek ceny bagażu", "status": f"1 € = {rate:.2f} zł".replace(".", ",")},
                {"name": "trivago", "role": "Noclegi: cena za pobyt, ocena, zdjęcie", "status": f"{len(picked) - stay_errors}/{len(picked)} wyszukiwań"},
                {"name": "Open-Meteo", "role": "Prognoza lub średnia pogoda", "status": "ok"},
            ],
        },
        "deals": deals,
    }
    publish(site_dir, payload, site_url=s.site_url, bag=s.default_bag, bag_label=BAG_OPTIONS[s.default_bag]["short"],
            keep_days=s.archive_days)
    history.save_fares(state_dir, stored, today_typical, today)
    log.info("published %d deals in %ss", len(deals), payload["stats"]["duration_s"])
    return payload
