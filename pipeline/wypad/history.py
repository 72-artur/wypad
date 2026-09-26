"""Small persistent memory between daily runs (committed to the repo under state/):
per-route median fares for a "typical price" baseline, and yesterday's deals for "new"/"cheaper" badges."""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from pathlib import Path

from .output import read_json, write_json

KEEP_DAYS = 45


def load_fares(state_dir: Path) -> dict:
    return read_json(state_dir / "fares.json", {}) or {}


def typical_with_history(today_typical: dict[str, float], stored: dict, today: date) -> dict[str, float]:
    """Median of the daily route medians over the last 30 days, including today's."""
    cutoff = (today - timedelta(days=30)).isoformat()
    out = {}
    for route in set(today_typical) | set(stored):
        series = [v for d, v in (stored.get(route) or {}).items() if d >= cutoff and d != today.isoformat()]
        if route in today_typical:
            series.append(today_typical[route])
        if series:
            out[route] = float(statistics.median(series))
    return out


def save_fares(state_dir: Path, stored: dict, today_typical: dict[str, float], today: date) -> None:
    cutoff = (today - timedelta(days=KEEP_DAYS)).isoformat()
    for route, v in today_typical.items():
        stored.setdefault(route, {})[today.isoformat()] = round(v, 2)
    pruned = {r: {d: v for d, v in days.items() if d >= cutoff} for r, days in stored.items()}
    write_json(state_dir / "fares.json", {r: days for r, days in pruned.items() if days})


def previous_payload(site_dir: Path, today: date) -> dict | None:
    """Most recent archived day before today (usually yesterday)."""
    days = sorted(p.stem for p in (site_dir / "data" / "archive").glob("*.json") if p.stem < today.isoformat())
    return read_json(site_dir / "data" / "archive" / f"{days[-1]}.json") if days else None


def mark_changes(deals: list[dict], previous: dict | None, bag: str, min_drop: int = 30) -> None:
    """'new' = not offered in the previous run; price_drop = previous total minus today's (same trip)."""
    if not previous or previous.get("sample"):
        return
    before = {d["id"]: d for d in previous.get("deals", [])}
    for d in deals:
        old = before.get(d["id"])
        if old is None:
            d["labels"].append("new")
            continue
        drop = round(old["totals"].get(bag, 0) - d["totals"][bag])
        if drop >= min_drop:
            d["price_drop"] = drop
