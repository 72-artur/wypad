"""Accommodation offers from trivago's public MCP server (no key; JSON-RPC over HTTP).

Research 2026-09-25 (docs/RESEARCH.md): works from a plain script, returns 25 properties per search
with the total price for the stay in PLN, trivago's aggregated guest rating, stars, coordinates, the
advertiser with the best deal and a trivago link that keeps the dates and 2 adults. It does not
return the city's absolute cheapest offers, so we run three searches per trip
and filter/rank ourselves. No published terms or rate limits: keep volume low (~60 calls/day).
"""
from __future__ import annotations

import json
import logging
import math
import re
from datetime import date
from urllib.parse import urlencode

import requests

from ..http import UA

log = logging.getLogger(__name__)
MCP_URL = "https://mcp.trivago.com/mcp"
PROTOCOL = "2025-06-18"
HOSTEL_WORDS = re.compile(r"hostel|backpack|youth|dorm|capsule|kapsu|camping|kemping|pod hotel|ostello|"
                          r"jugendherberge|auberge de jeunesse|albergue", re.I)
APARTMENT_WORDS = re.compile(r"apart|flat|suites?\b|residen|loft|studio", re.I)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * 6371 * math.asin(math.sqrt(a))


def parse_pln(s) -> int | None:
    """'1 333 zł' (spaces may be NBSP) → 1333; '1,965' → 1965."""
    digits = re.sub(r"[^\d]", "", str(s or ""))
    return int(digits) if digits else None


def booking_search_url(query: str, check_in: str, check_out: str, adults: int = 2) -> str:
    """Booking.com search by free text (hotel name + city) with dates and guests prefilled."""
    return "https://www.booking.com/searchresults.pl.html?" + urlencode({
        "ss": query, "checkin": check_in, "checkout": check_out, "group_adults": adults,
        "no_rooms": 1, "group_children": 0, "selected_currency": "PLN"})


def booking_city_url(city: str, check_in: str, check_out: str, adults: int = 2) -> str:
    """City search on Booking.com: cheapest first, guest score 8+, hotels only (keeps dorm beds out), < 3 km."""
    return booking_search_url(city, check_in, check_out, adults) + "&order=price&nflt=" + \
        "review_score%3D80%3Bht_id%3D204%3Bdistance%3D3000"


def _decode(resp: requests.Response):
    """The server answers JSON, but MCP allows SSE framing; accept both."""
    text = resp.text.strip()
    if not text:
        return None
    if text.startswith("{"):
        return json.loads(text)
    data = [ln[5:].strip() for ln in text.splitlines() if ln.startswith("data:")]
    return json.loads(data[-1]) if data else None


class Trivago:
    name = "trivago"

    def __init__(self, timeout: float = 90):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Content-Type": "application/json",
                               "Accept": "application/json, text/event-stream"})
        self.timeout = timeout
        self.session_id: str | None = None
        self.calls = 0
        self._id = 0

    def _post(self, payload: dict):
        headers = {}
        if self.session_id:
            headers = {"Mcp-Session-Id": self.session_id, "MCP-Protocol-Version": PROTOCOL}
        r = self.s.post(MCP_URL, data=json.dumps(payload), headers=headers, timeout=self.timeout)
        self.calls += 1
        return r

    def _connect(self) -> None:
        self._id += 1
        r = self._post({"jsonrpc": "2.0", "id": self._id, "method": "initialize", "params": {
            "protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "wypad", "version": "1.0"}}})
        r.raise_for_status()
        self.session_id = r.headers.get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("trivago MCP: no session id in initialize response")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _search(self, args: dict) -> list[dict]:
        for attempt in range(2):
            if not self.session_id:
                self._connect()
            self._id += 1
            r = self._post({"jsonrpc": "2.0", "id": self._id, "method": "tools/call",
                            "params": {"name": "trivago-accommodation-radius-search", "arguments": args}})
            if r.status_code in (400, 404) and attempt == 0:   # session expired → reconnect once
                self.session_id = None
                continue
            r.raise_for_status()
            body = _decode(r) or {}
            if "error" in body:
                raise RuntimeError(f"trivago MCP error: {body['error']}")
            sc = (body.get("result") or {}).get("structuredContent") or {}
            if sc.get("validation_errors") or sc.get("error"):
                raise RuntimeError(f"trivago tool error: {sc.get('validation_errors') or sc.get('error')}")
            return sc.get("accommodations") or []
        return []

    def offers(self, lat: float, lon: float, check_in: date, check_out: date, adults: int = 2) -> list[dict]:
        base = {"latitude": lat, "longitude": lon, "arrival": check_in.isoformat(), "departure": check_out.isoformat(),
                "adults": adults, "rooms": 1, "country": "PL", "currency": "PLN", "language": "PL_PL",
                "review_rating": {"rating80": True}}
        seen: dict[str, dict] = {}
        # Results come in trivago's relevance order, not by price, and each filter surfaces a different
        # set; three variants (any / 2–3★ / with kitchen = apartments) cover the cheaper end much better.
        for extra in ({}, {"hotel_rating": {"2star": True, "3star": True}}, {"filters": {"kitchen": True}}):
            try:
                for a in self._search({**base, **extra}):
                    seen.setdefault(a.get("accommodation_id") or a.get("accommodation_name"), a)
            except Exception as e:  # noqa: BLE001 — one failed variant should not lose the other
                log.warning("trivago search %s failed: %s", extra or "default", e)
        return [o for a in seen.values() if (o := normalize(a, lat, lon, check_in, check_out))]


def normalize(a: dict, lat: float, lon: float, check_in: date, check_out: date) -> dict | None:
    total = parse_pln(a.get("price_per_stay"))
    if not total or a.get("currency") not in (None, "PLN"):
        return None
    nights = (check_out - check_in).days
    try:
        rating = float(a["review_rating"]) if a.get("review_rating") else None
    except ValueError:
        rating = None
    stars = int(a["hotel_rating"]) if str(a.get("hotel_rating") or "").isdigit() else 0
    name = (a.get("accommodation_name") or "").strip()
    dist = (round(haversine_km(lat, lon, a["latitude"], a["longitude"]), 1)
            if a.get("latitude") is not None and a.get("longitude") is not None else None)
    apartment = bool(APARTMENT_WORDS.search(name))
    return {
        "id": a.get("accommodation_id"),
        "name": name,
        "kind": "Apartament" if apartment and stars < 2 else (f"Hotel {stars}★" if stars else "Obiekt"),
        "stars": stars or None,
        "apartment": apartment,
        "hostel_like": bool(HOSTEL_WORDS.search(name)),
        "rating": rating,
        "rating_source": "trivago",
        "reviews": parse_pln(a.get("review_count")),
        "distance_km": dist,
        "lat": a.get("latitude"), "lon": a.get("longitude"),
        "image": a.get("main_image") if str(a.get("main_image", "")).startswith("https://") else None,
        "amenities": [x.strip() for x in (a.get("top_amenities") or "").split(",") if x.strip()][:6],
        "price_total": total,
        "price_night": round(total / max(nights, 1)),
        "provider": a.get("advertisers") or None,
        "trivago_url": a.get("accommodation_url") if str(a.get("accommodation_url", "")).startswith("https://") else None,
    }


def pick_stays(offers: list[dict], *, min_rating: float, max_km: float, min_reviews: int = 100) -> list[dict]:
    """Cheapest eligible stay first, then up to 2 alternatives. Relaxes distance, then review count,
    before giving up — never the rating floor Artur asked for."""
    def eligible(o, km, reviews):
        return (o["rating"] is not None and o["rating"] >= min_rating and not o["hostel_like"]
                and (o["stars"] or 0) + (2 if o["apartment"] else 0) >= 2
                and o["distance_km"] is not None and o["distance_km"] <= km
                and (o["reviews"] or 0) >= reviews)

    for km, reviews in ((max_km, min_reviews), (max_km * 5 / 3, min_reviews), (max_km * 5 / 3, 30)):
        ok = sorted((o for o in offers if eligible(o, km, reviews)), key=lambda o: (o["price_total"], -(o["rating"] or 0)))
        if ok:
            best = ok[0]
            # Alternatives: better rated or closer options, cheapest first.
            alts = [o for o in ok[1:] if (o["rating"] or 0) > (best["rating"] or 0) or (o["distance_km"] or 9) < (best["distance_km"] or 9)]
            return [best] + alts[:2]
    return []
