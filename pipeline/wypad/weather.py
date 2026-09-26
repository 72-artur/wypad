"""Weather for the trip dates from Open-Meteo (free, no key): forecast when the trip starts within
~2 weeks, otherwise the average of the same calendar days in the last 3 years ("średnio o tej porze")."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)
FORECAST_DAYS = 15
YEARS_BACK = 3
ARCHIVE_TIMEOUT_S = 15
# (lat, lon, start, end) → daily history. Small per-year windows: one 5-year request timed out
# repeatedly from GitHub's runners (2026-09-26), a few days per year answers in well under a second.
_ARCHIVE: dict[tuple, dict] = {}

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


def _years_earlier(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year - years)
    except ValueError:                          # 29 February
        return d.replace(year=d.year - years, day=28)


def trip_weather(lat: float, lon: float, start: date, end: date, today: date, session=requests) -> dict | None:
    try:
        if (start - today).days <= FORECAST_DAYS - (end - start).days - 1:
            r = session.get("https://api.open-meteo.com/v1/forecast", timeout=20, params={
                "latitude": lat, "longitude": lon, "timezone": "auto",
                "daily": "temperature_2m_max,precipitation_probability_max,weather_code",
                "start_date": start.isoformat(), "end_date": end.isoformat()})
            r.raise_for_status()
            return summarize_forecast(r.json().get("daily", {}))
        merged: dict[str, list] = {"time": [], "temperature_2m_max": [], "precipitation_sum": []}
        for back in range(1, YEARS_BACK + 1):
            s0, e0 = _years_earlier(start, back), _years_earlier(end, back)
            if e0 > today - timedelta(days=7):     # the archive lags a few days behind
                continue
            key = (lat, lon, s0, e0)
            if key not in _ARCHIVE:
                try:
                    r = session.get("https://archive-api.open-meteo.com/v1/archive", timeout=ARCHIVE_TIMEOUT_S, params={
                        "latitude": lat, "longitude": lon, "timezone": "auto",
                        "daily": "temperature_2m_max,precipitation_sum",
                        "start_date": s0.isoformat(), "end_date": e0.isoformat()})
                    r.raise_for_status()
                    _ARCHIVE[key] = r.json().get("daily", {})
                except Exception as e:  # noqa: BLE001 — one missing year still leaves an average
                    log.warning("weather archive %s,%s %s failed: %s", lat, lon, s0.year, e)
                    continue
            for k in merged:
                merged[k] += _ARCHIVE[key].get(k, [])
        return summarize_climate(merged, start, end)
    except Exception as e:  # noqa: BLE001 — weather is optional decoration
        log.warning("weather failed for %s,%s: %s", lat, lon, e)
        return None
