"""Weather for the trip dates from Open-Meteo (free, no key): forecast when the trip starts within
~2 weeks, otherwise the 5-year average for the same calendar days ("średnio o tej porze")."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)
FORECAST_DAYS = 15
_ARCHIVE: dict[tuple, dict] = {}  # (lat, lon) → daily history; one download per city per run

WMO_PL = [
    ((0,), "słonecznie", "sun"),
    ((1,), "przeważnie słonecznie", "sun"),
    ((2,), "częściowe zachmurzenie", "cloud-sun"),
    ((3,), "pochmurno", "cloud-sun"),
    ((45, 48), "mgła", "cloud-sun"),
    ((51, 53, 55, 56, 57), "mżawka", "cloud-rain"),
    ((61, 63, 65, 66, 67), "deszcz", "cloud-rain"),
    ((71, 73, 75, 77, 85, 86), "śnieg", "cloud-rain"),
    ((80, 81, 82), "przelotne opady", "cloud-rain"),
    ((95, 96, 99), "burze", "cloud-rain"),
]


def describe(code: int) -> tuple[str, str]:
    for codes, text, icon in WMO_PL:
        if code in codes:
            return text, icon
    return "zmiennie", "cloud-sun"


def summarize_forecast(daily: dict) -> dict | None:
    temps = [t for t in daily.get("temperature_2m_max", []) if t is not None]
    codes = [c for c in daily.get("weather_code", []) if c is not None]
    if not temps:
        return None
    text, icon = describe(Counter(codes).most_common(1)[0][0]) if codes else ("", "cloud-sun")
    rain = max([p for p in daily.get("precipitation_probability_max", []) if p is not None] or [0])
    if rain >= 60 and "deszcz" not in text and "opady" not in text:
        text = f"{text}, możliwy deszcz" if text else "możliwy deszcz"
    return {"kind": "forecast", "t_max": round(sum(temps) / len(temps)), "text": f"prognoza: {text}", "icon": icon}


def _same_season(d: date, start: date, end: date) -> bool:
    """Is day d (any year) within the trip's month/day window?"""
    key = (d.month, d.day)
    a, b = (start.month, start.day), (end.month, end.day)
    return a <= key <= b if a <= b else key >= a or key <= b


def summarize_climate(daily: dict, start: date, end: date) -> dict | None:
    temps, wet = [], 0
    for ds, t, p in zip(daily.get("time", []), daily.get("temperature_2m_max", []), daily.get("precipitation_sum", [])):
        if t is None or not _same_season(date.fromisoformat(ds), start, end):
            continue
        temps.append(t)
        wet += 1 if (p or 0) >= 1.0 else 0
    if len(temps) < 3:
        return None
    wet_pct = round(100 * wet / len(temps))
    return {"kind": "climate", "t_max": round(sum(temps) / len(temps)),
            "text": f"średnio o tej porze, deszcz w {wet_pct}% dni", "icon": "cloud-rain" if wet_pct >= 40 else "cloud-sun"}


def trip_weather(lat: float, lon: float, start: date, end: date, today: date, session=requests) -> dict | None:
    try:
        if (start - today).days <= FORECAST_DAYS - (end - start).days - 1:
            r = session.get("https://api.open-meteo.com/v1/forecast", timeout=20, params={
                "latitude": lat, "longitude": lon, "timezone": "auto",
                "daily": "temperature_2m_max,precipitation_probability_max,weather_code",
                "start_date": start.isoformat(), "end_date": end.isoformat()})
            r.raise_for_status()
            return summarize_forecast(r.json().get("daily", {}))
        if (lat, lon) not in _ARCHIVE:
            r = session.get("https://archive-api.open-meteo.com/v1/archive", timeout=30, params={
                "latitude": lat, "longitude": lon, "timezone": "auto", "daily": "temperature_2m_max,precipitation_sum",
                "start_date": date(today.year - 5, 1, 1).isoformat(), "end_date": (today - timedelta(days=7)).isoformat()})
            r.raise_for_status()
            _ARCHIVE[(lat, lon)] = r.json().get("daily", {})
        return summarize_climate(_ARCHIVE[(lat, lon)], start, end)
    except Exception as e:  # noqa: BLE001 — weather is optional decoration
        log.warning("weather failed for %s,%s: %s", lat, lon, e)
        return None
