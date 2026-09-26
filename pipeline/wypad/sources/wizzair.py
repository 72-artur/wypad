"""Wizz Air fares from the public endpoints that wizzair.com itself uses (no key; unofficial).

- API version: read from the wizzair.com page (`apiUrl:"https://be.wizzair.com/<version>/Api"`).
- routes:     GET  /asset/map?languageCode=pl-pl (direct connections; city-alias stations such as LON excluded)
- fares:      POST /search/timetable — the cheapest price per day with its departure time, both directions
              in one call. Date windows must stay under ~38 days (41+ days → HTTP 400, checked 2026-09-26).

Compared with Ryanair (research 2026-09-25): prices are PER PERSON without a guarantee of 2 seats,
and there are no arrival times or flight numbers. Arrival is estimated from the distance and the time
zones and is shown in the app with "~". Days with several flights are skipped, because the timetable
does not say which of them has the listed price.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from ..http import Http

HOME = "https://wizzair.com/pl-pl"
WINDOW_DAYS = 30
HEADERS = {"Origin": "https://wizzair.com", "Referer": "https://wizzair.com/", "Content-Type": "application/json"}

# Country code (from the Wizz route map) → time zone, for arrival estimates.
TZ = {
    "PL": "Europe/Warsaw", "GB": "Europe/London", "IE": "Europe/Dublin", "PT": "Europe/Lisbon", "ES": "Europe/Madrid",
    "FR": "Europe/Paris", "IT": "Europe/Rome", "DE": "Europe/Berlin", "NL": "Europe/Amsterdam", "BE": "Europe/Brussels",
    "LU": "Europe/Luxembourg", "CH": "Europe/Zurich", "AT": "Europe/Vienna", "CZ": "Europe/Prague", "SK": "Europe/Bratislava",
    "HU": "Europe/Budapest", "DK": "Europe/Copenhagen", "NO": "Europe/Oslo", "SE": "Europe/Stockholm", "FI": "Europe/Helsinki",
    "IS": "Atlantic/Reykjavik", "EE": "Europe/Tallinn", "LV": "Europe/Riga", "LT": "Europe/Vilnius", "GR": "Europe/Athens",
    "HR": "Europe/Zagreb", "SI": "Europe/Ljubljana", "RS": "Europe/Belgrade", "BA": "Europe/Sarajevo", "AL": "Europe/Tirane",
    "ME": "Europe/Podgorica", "MK": "Europe/Skopje", "BG": "Europe/Sofia", "RO": "Europe/Bucharest", "MD": "Europe/Chisinau",
    "MT": "Europe/Malta", "TR": "Europe/Istanbul", "CY": "Asia/Nicosia", "GE": "Asia/Tbilisi",
}


def booking_url(origin: str, dest: str, out_date: str, back_date: str, adults: int = 2) -> str:
    """wizzair.com flight selection with route, dates and passengers (format from the research; the page
    parses route and dates, the flight list itself was not verifiable in an automated browser)."""
    return f"https://www.wizzair.com/pl-pl/booking/select-flight/{origin}/{dest}/{out_date}/{back_date}/{adults}/0/0/null"


def flight_minutes(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Block time estimate: 40 min taxi/climb/descent + 750 km/h, rounded to 5 min.
    Checked against real schedules: POZ–BSL ~105 min, WRO–LTN ~130 min, WRO–BCN ~160 min."""
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    km = 2 * 6371 * math.asin(math.sqrt(a))
    return int(round((40 + km / 12.5) / 5) * 5)


def estimate_arrival(dep_local: str, frm: dict, to: dict) -> str:
    """Local departure at `frm` → estimated local arrival at `to` ('YYYY-MM-DDTHH:MM')."""
    dep = datetime.fromisoformat(dep_local[:16]).replace(tzinfo=ZoneInfo(TZ.get(frm.get("cc"), "Europe/Warsaw")))
    arr = dep + timedelta(minutes=flight_minutes(frm["lat"], frm["lon"], to["lat"], to["lon"]))
    return arr.astimezone(ZoneInfo(TZ.get(to.get("cc"), "Europe/Warsaw"))).strftime("%Y-%m-%dT%H:%M")


def _days(flights: list[dict]) -> dict[date, tuple[str, float]]:
    """{day: (departure 'YYYY-MM-DDTHH:MM', price per person)} for days with one flight and a known price."""
    out = {}
    for f in flights or []:
        times = f.get("departureDates") or []
        price = (f.get("price") or {}).get("amount") or 0
        if f.get("priceType") != "price" or price <= 0 or len(times) != 1 or (f.get("price") or {}).get("currencyCode") != "PLN":
            continue
        out[date.fromisoformat(times[0][:10])] = (times[0][:16], float(price))
    return out


class WizzAir:
    name = "Wizz Air"
    code = "W6"

    def __init__(self, http: Http):
        self.http = http
        self._api: str | None = None
        self._stations: dict[str, dict] | None = None
        self._failed: str | None = None

    def api(self) -> str:
        if self._failed:
            raise RuntimeError(self._failed)          # fail fast for the remaining origins of this run
        if not self._api:
            try:
                html = self.http.get_text(HOME)
                m = re.search(r'apiUrl:"(https://be\.wizzair\.com/\d+\.\d+\.\d+/Api)"', html)
                if not m:
                    raise RuntimeError("API version not found on wizzair.com")
                self._api = m.group(1)
            except Exception as e:  # noqa: BLE001
                self._failed = f"Wizz Air niedostępny: {e}"
                raise RuntimeError(self._failed) from e
        return self._api

    def stations(self) -> dict[str, dict]:
        if self._stations is None:
            data = self.http.get_json(f"{self.api()}/asset/map", params={"languageCode": "pl-pl"})
            self._stations = {c["iata"]: c for c in data.get("cities", [])}
        return self._stations

    def _geo(self, iata: str) -> dict:
        c = self.stations().get(iata, {})
        return {"lat": c.get("latitude"), "lon": c.get("longitude"), "cc": c.get("countryCode"), "name": c.get("shortName")}

    def routes(self, origin: str) -> dict[str, dict]:
        st = self.stations()
        conns = (st.get(origin) or {}).get("connections") or []
        return {c["iata"]: {"name": (st.get(c["iata"]) or {}).get("shortName")}
                for c in conns if c.get("isDirectFlight") and not (st.get(c["iata"]) or {}).get("isFakeStation")}

    def round_trips(self, origin: str, dest: str, out_from: date, out_to: date,
                    back_to: date, nights_min: int, nights_max: int) -> list[dict]:
        outs: dict[date, tuple[str, float]] = {}
        backs: dict[date, tuple[str, float]] = {}
        failures: list[str] = []
        windows = 0
        start = out_from
        while start <= out_to:
            end = min(start + timedelta(days=WINDOW_DAYS - 1), out_to)
            back_end = min(end + timedelta(days=nights_max + 1), back_to)
            body = {"flightList": [
                {"departureStation": origin, "arrivalStation": dest, "from": start.isoformat(), "to": end.isoformat()},
                {"departureStation": dest, "arrivalStation": origin, "from": start.isoformat(), "to": back_end.isoformat()}],
                "priceType": "regular", "adultCount": 2, "childCount": 0, "infantCount": 0}
            try:
                data = self.http.post_json(f"{self.api()}/search/timetable", body, headers=self._headers())
                outs.update(_days(data.get("outboundFlights")))
                backs.update(_days(data.get("returnFlights")))
            except Exception as e:  # noqa: BLE001 — keep the other window's fares
                failures.append(str(e))
            windows += 1
            start = end + timedelta(days=1)
        if failures and len(failures) == windows:
            raise RuntimeError(failures[0])
        return self._pair(origin, dest, outs, backs, nights_min, nights_max)

    def _headers(self) -> dict:
        """The first timetable call sets an anti-forgery cookie; every later call in the session is rejected
        ("InvalidProtocol", HTTP 400) unless the token is echoed in X-RequestVerificationToken, as the site does."""
        token = next((c.value for c in self.http.s.cookies if c.name == "RequestVerificationToken"), None)
        return {**HEADERS, "X-RequestVerificationToken": token} if token else dict(HEADERS)

    def _pair(self, origin, dest, outs, backs, nights_min, nights_max) -> list[dict]:
        o_geo, d_geo = self._geo(origin), self._geo(dest)
        if None in (o_geo["lat"], d_geo["lat"]):
            return []
        combos = []
        for od, (out_dep, out_pp) in sorted(outs.items()):
            for bd, (back_dep, back_pp) in sorted(backs.items()):
                if not nights_min <= (bd - od).days <= nights_max:
                    continue
                combos.append({
                    "carrier": "Wizz Air", "carrier_code": "W6",
                    "origin": origin, "dest": dest, "origin_name": o_geo["name"], "dest_name": d_geo["name"],
                    "out_dep": out_dep, "out_arr": estimate_arrival(out_dep, o_geo, d_geo), "out_no": None,
                    "back_dep": back_dep, "back_arr": estimate_arrival(back_dep, d_geo, o_geo), "back_no": None,
                    "fare_pp": round(out_pp + back_pp, 2), "fare_total": round(2 * (out_pp + back_pp), 2),
                    "prev_total": None, "arr_estimated": True, "two_seats_confirmed": False,
                })
        return combos
