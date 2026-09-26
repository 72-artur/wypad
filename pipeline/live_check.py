"""Is today's data already live on the site? First step of the daily workflow, before Python deps are
installed, so it uses only the standard library. Prints `done=true|false` for $GITHUB_OUTPUT.

Kept outside the `wypad` package on purpose: running a script from `wypad/` would put `wypad/http.py`
in front of the standard `http` module.
Usage: python3 pipeline/live_check.py <site_url> [force]
"""
from __future__ import annotations

import json
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo


def published_date(site_url: str, opener=urllib.request.urlopen) -> str | None:
    try:
        with opener(f"{site_url}/data/deals.json", timeout=20) as r:
            data = json.load(r)
        return None if data.get("sample") else data.get("date")
    except Exception:  # noqa: BLE001 — no site yet, network error, bad JSON: all mean "not published"
        return None


def decide(site_url: str, force: bool, today: str, opener=urllib.request.urlopen) -> tuple[bool, str | None]:
    live = published_date(site_url, opener)
    return (live == today and not force), live


def main(argv: list[str]) -> int:
    site_url = argv[0].rstrip("/")
    force = len(argv) > 1 and argv[1].lower() == "true"
    today = datetime.now(ZoneInfo("Europe/Warsaw")).date().isoformat()
    done, live = decide(site_url, force, today)
    print(f"Dziś: {today}, na stronie: {live or 'brak'}, wymuszenie: {force}", file=sys.stderr)
    print(f"done={'true' if done else 'false'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
