"""Weather for the trip dates from Open-Meteo (free, no key).

- Trips starting within ~2 weeks: the forecast (fast API, works from GitHub's runners).
- Later trips: the city's monthly climate over the last 3 full years ("średnio o tej porze").
  Open-Meteo's archive API timed out on most requests from GitHub's runners (2026-09-26) while
  answering in < 1 s from a home connection, so the climate is built once locally
  (`python -m wypad climate --state ../state`) and kept in state/climate.json. The daily run only
  fetches cities that are missing, within a small time budget.
"""
from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import date
from pathlib import Path

import requests

from .output import read_json, write_json

log = logging.getLogger(__name__)
FORECAST_DAYS = 15
CLIMATE_YEARS = 3
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

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


def monthly_climate(daily: dict) -> dict[str, dict]:
    """{"01": {"t_max": 14, "wet_pct": 35}, ...} from a daily archive series (months with ≥ 20 days)."""
    by_month: dict[str, list[tuple[float, float]]] = {}
    for ds, t, p in zip(daily.get("time", []), daily.get("temperature_2m_max", []), daily.get("precipitation_sum", [])):
        if t is not None:
            by_month.setdefault(ds[5:7], []).append((t, p or 0.0))
    return {m: {"t_max": round(sum(t for t, _ in v) / len(v)), "wet_pct": round(100 * sum(1 for _, p in v if p >= 1.0) / len(v))}
            for m, v in sorted(by_month.items()) if len(v) >= 20}


def climate_summary(stats: dict | None) -> dict | None:
    if not stats:
        return None
    return {"kind": "climate", "t_max": stats["t_max"], "text": f"średnio o tej porze, deszcz w {stats['wet_pct']}% dni",
            "icon": "cloud-rain" if stats["wet_pct"] >= 40 else "cloud-sun"}


def fetch_city_climate(lat: float, lon: float, today: date, session=requests, timeout: float = 60) -> dict[str, dict]:
    r = session.get(ARCHIVE_URL, timeout=timeout, params={
        "latitude": lat, "longitude": lon, "timezone": "auto", "daily": "temperature_2m_max,precipitation_sum",
        "start_date": f"{today.year - CLIMATE_YEARS}-01-01", "end_date": f"{today.year - 1}-12-31"})
    r.raise_for_status()
    return monthly_climate(r.json().get("daily", {}))


class Weather:
    """Forecast for near trips, cached monthly climate for later ones; never raises."""

    def __init__(self, state_dir: Path | None = None, session=requests, archive_budget_s: float = 60,
                 clock=time.monotonic):
        self.path = state_dir / "climate.json" if state_dir else None
        self.cache: dict[str, dict] = (read_json(self.path, {}) or {}) if self.path else {}
        self.session, self.clock = session, clock
        self.deadline = clock() + archive_budget_s
        self.dirty = False
        self.failed: set[str] = set()

    def trip(self, city_key: str, lat: float, lon: float, start: date, end: date, today: date) -> dict | None:
        try:
            if (start - today).days <= FORECAST_DAYS - (end - start).days - 1:
                r = self.session.get(FORECAST_URL, timeout=20, params={
                    "latitude": lat, "longitude": lon, "timezone": "auto",
                    "daily": "temperature_2m_max,precipitation_probability_max,weather_code",
                    "start_date": start.isoformat(), "end_date": end.isoformat()})
                r.raise_for_status()
                return summarize_forecast(r.json().get("daily", {}))
        except Exception as e:  # noqa: BLE001 — weather is optional decoration
            log.warning("forecast failed for %s: %s", city_key, e)
            return None
        month = f"{start.month:02d}"
        if city_key not in self.cache and city_key not in self.failed and self.clock() < self.deadline:
            try:
                timeout = max(5.0, min(30.0, self.deadline - self.clock()))
                self.cache[city_key] = fetch_city_climate(lat, lon, today, self.session, timeout=timeout)
                self.dirty = True
            except Exception as e:  # noqa: BLE001
                log.warning("climate for %s unavailable: %s", city_key, e)
                self.failed.add(city_key)
        return climate_summary(self.cache.get(city_key, {}).get(month))

    def save(self) -> None:
        if self.path and self.dirty:
            write_json(self.path, self.cache)


def build_climate(state_dir: Path, cities: dict[str, tuple], today: date, session=requests, pause_s: float = 0.5) -> dict:
    """One-off (and re-runnable) local job: monthly climate for every destination city."""
    path = state_dir / "climate.json"
    cache = read_json(path, {}) or {}
    for key, (name, _country, _cc, lat, lon, *_rest) in cities.items():
        if key in cache:
            continue
        try:
            cache[key] = fetch_city_climate(lat, lon, today, session)
            log.info("climate: %s ok (%d months)", name, len(cache[key]))
        except Exception as e:  # noqa: BLE001
            log.warning("climate: %s failed: %s", name, e)
        write_json(path, cache)
        time.sleep(pause_s)
    return cache
