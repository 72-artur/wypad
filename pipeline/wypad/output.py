"""Writes what the static site reads: today's deals, a dated archive (so shared links keep working)
and one tiny HTML page per deal with Open Graph tags for rich link previews in iMessage/WhatsApp."""
from __future__ import annotations

import html
import json
import logging
import re
from datetime import date, timedelta
from pathlib import Path

from .config import ORIGINS

log = logging.getLogger(__name__)


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def share_path(day: str, deal_id: str) -> str:
    return f"d/{day}/{deal_id}.html"


def _pln(x: float) -> str:
    n = int(round(x))
    return f"{n:,}".replace(",", " ") + " zł" if n >= 10000 else f"{n} zł"


def share_page(deal: dict, *, day: str, site_url: str, bag: str, bag_label: str) -> str:
    """Static page: crawlers read the OG tags, people get redirected into the app."""
    target = f"../../#/d/{day}/{deal['id']}"
    stay = deal.get("stay") or {}
    out, back = deal["trip"]["out_date"], deal["trip"]["back_date"]
    est = bool(((deal.get("flight") or {}).get("bags") or {}).get(bag, {}).get("estimated"))
    title = (f"{deal['city']['name']} {out[8:10]}.{out[5:7]}–{back[8:10]}.{back[5:7]}: "
             f"{'ok. ' if est else ''}{_pln(deal['totals'][bag])} za 2 osoby")
    rating = f" ({stay['rating']:.1f}/10)".replace(".", ",") if stay.get("rating") else ""
    origin = deal["flight"]["out"]["from"]
    origin_gen = ORIGINS.get(origin, {}).get("city_gen") or origin
    desc = (f"Lot {deal['flight']['carrier']} z {origin_gen}, bagaż: {bag_label}{' (szacunek)' if est else ''}, "
            f"nocleg: {stay.get('name', '—')}{rating}. Lot, bagaż i nocleg w jednej cenie.")
    image = stay.get("image") if str(stay.get("image", "")).startswith("https://") else (f"{site_url}/icons/og-default.png" if site_url else "")
    url = f"{site_url}/{share_path(day, deal['id'])}" if site_url else ""
    e = html.escape
    return f"""<!doctype html>
<html lang="pl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · Wypad</title>
<meta name="description" content="{e(desc)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Wypad">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
{f'<meta property="og:image" content="{e(image)}">' if image else ''}
{f'<meta property="og:url" content="{e(url)}">' if url else ''}
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="noindex">
<meta http-equiv="refresh" content="0; url={e(target)}">
<script>location.replace({json.dumps(target)});</script>
</head><body style="font-family:system-ui,sans-serif;padding:24px">
<p><a href="{e(target)}">Otwórz propozycję w aplikacji Wypad</a></p>
</body></html>
"""


def absolutize_index_og(site_dir: Path, site_url: str) -> None:
    """Link-preview crawlers need absolute URLs; the site URL is only known on GitHub (WYPAD_SITE_URL)."""
    index = site_dir / "index.html"
    if not site_url or not index.exists():
        return
    text = index.read_text(encoding="utf-8")
    new = re.sub(r'(<meta property="og:image" content=")[^"]*(")', rf'\g<1>{site_url}/icons/og-default.png\g<2>', text)
    if 'property="og:url"' not in new:
        new = new.replace('<meta property="og:image"', f'<meta property="og:url" content="{site_url}/">\n  <meta property="og:image"', 1)
    if new != text:
        index.write_text(new, encoding="utf-8")


def publish(site_dir: Path, payload: dict, *, site_url: str, bag: str, bag_label: str, keep_days: int) -> None:
    day = payload["date"]
    for deal in payload["deals"]:
        deal["share_path"] = share_path(day, deal["id"])
    write_json(site_dir / "data" / "deals.json", payload)
    # A same-day re-run (manual "force") must not break links already sent in the morning push:
    # deals that disappeared stay in the day's archive under "replaced" and keep their share pages.
    old = read_json(site_dir / "data" / "archive" / f"{day}.json", {}) or {}
    ids = {d["id"] for d in payload["deals"]}
    replaced = [d for d in old.get("deals", []) + old.get("replaced", []) if d["id"] not in ids]
    write_json(site_dir / "data" / "archive" / f"{day}.json", {**payload, "replaced": replaced} if replaced else payload)
    absolutize_index_og(site_dir, site_url)
    for deal in payload["deals"]:
        p = site_dir / share_path(day, deal["id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(share_page(deal, day=day, site_url=site_url, bag=bag, bag_label=bag_label), encoding="utf-8")
    prune(site_dir, today=date.fromisoformat(day), keep_days=keep_days)


def prune(site_dir: Path, *, today: date, keep_days: int) -> None:
    cutoff = today - timedelta(days=keep_days)
    for f in (site_dir / "data" / "archive").glob("*.json"):
        try:
            if date.fromisoformat(f.stem) < cutoff:
                f.unlink()
        except ValueError:
            continue
    for d in (site_dir / "d").glob("*"):
        try:
            if d.is_dir() and date.fromisoformat(d.name) < cutoff:
                for f in d.glob("*"):
                    f.unlink()
                d.rmdir()
        except ValueError:
            continue
