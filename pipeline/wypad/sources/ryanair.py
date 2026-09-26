"""Ryanair fare data from the public endpoints that ryanair.com itself uses (no key; unofficial).

- routes:      /api/views/locate/searchWidget/routes/pl/airport/{IATA}
- round trips: /api/farfnd/v4/roundTripFares (one call per origin+destination returns every date
               combination in the window). With adultPaxCount=2 the price is the TOTAL for 2 adults and only
               flights with 2 seats at that fare are returned (research 2026-09-25). Basic fare = small bag only.
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlencode

from ..http import Http

API = "https://www.ryanair.com/api"


def booking_url(origin: str, dest: str, out_date: str, back_date: str, adults: int = 2) -> str:
    """ryanair.com flight selection page prefilled with the route, dates and passengers."""
    q = {
        "adults": adults, "teens": 0, "children": 0, "infants": 0,
        "dateOut": out_date, "dateIn": back_date, "isConnectedFlight": "false", "discount": 0,
        "promoCode": "", "isReturn": "true", "originIata": origin, "destinationIata": dest,
        "tpAdults": adults, "tpTeens": 0, "tpChildren": 0, "tpInfants": 0,
        "tpStartDate": out_date, "tpEndDate": back_date, "tpDiscount": 0, "tpPromoCode": "",
        "tpOriginIata": origin, "tpDestinationIata": dest,
    }
    return "https://www.ryanair.com/pl/pl/trip/flights/select?" + urlencode(q)


class Ryanair:
    name = "Ryanair"
    code = "FR"

    def __init__(self, http: Http):
        self.http = http

    def routes(self, origin: str) -> dict[str, dict]:
        data = self.http.get_json(f"{API}/views/locate/searchWidget/routes/pl/airport/{origin}")
        out = {}
        for r in data:
            a = r.get("arrivalAirport") or {}
            if a.get("code"):
                out[a["code"]] = {"name": a.get("name"), "city": (a.get("city") or {}).get("name"),
                                  "country": (a.get("country") or {}).get("name")}
        return out

    def round_trips(self, origin: str, dest: str, out_from: date, out_to: date,
                    back_to: date, nights_min: int, nights_max: int) -> list[dict]:
        params = {
            "departureAirportIataCode": origin, "arrivalAirportIataCode": dest,
            "outboundDepartureDateFrom": out_from.isoformat(), "outboundDepartureDateTo": out_to.isoformat(),
            "inboundDepartureDateFrom": out_from.isoformat(), "inboundDepartureDateTo": back_to.isoformat(),
            "durationFrom": nights_min, "durationTo": nights_max,
            "market": "pl-pl", "adultPaxCount": 2, "currency": "PLN", "searchMode": "ALL",
        }
        data = self.http.get_json(f"{API}/farfnd/v4/roundTripFares", params=params)
        return [c for f in data.get("fares", []) if (c := self._normalize(f))]

    @staticmethod
    def _normalize(f: dict) -> dict | None:
        o, i, s = f.get("outbound") or {}, f.get("inbound") or {}, f.get("summary") or {}
        try:
            total = float(s["price"]["value"])   # for 2 adults
            if s["price"].get("currencyCode") != "PLN":
                return None
            return {
                "carrier": "Ryanair", "carrier_code": "FR",
                "origin": o["departureAirport"]["iataCode"], "dest": o["arrivalAirport"]["iataCode"],
                "origin_name": o["departureAirport"].get("name"), "dest_name": o["arrivalAirport"].get("name"),
                "out_dep": o["departureDate"][:16], "out_arr": o["arrivalDate"][:16], "out_no": o.get("flightNumber"),
                "back_dep": i["departureDate"][:16], "back_arr": i["arrivalDate"][:16], "back_no": i.get("flightNumber"),
                "fare_total": round(total, 2),
                "fare_pp": round(total / 2, 2),
                "prev_total": _prev(o, i),
            }
        except (KeyError, TypeError, ValueError):
            return None


def _prev(o: dict, i: dict) -> float | None:
    """Previous round-trip price (same passenger count), when Ryanair reports that a leg's price changed."""
    def leg_prev(leg: dict) -> float:
        p = leg.get("previousPrice")
        if isinstance(p, dict):
            p = p.get("value")
        return float(p) if p else float(leg["price"]["value"])

    if not o.get("previousPrice") and not i.get("previousPrice"):
        return None
    return round(leg_prev(o) + leg_prev(i), 2)
