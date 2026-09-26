"""CLI: `python -m wypad search --site ../site --state ../state` and `python -m wypad notify --site ../site`."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from .config import BAG_OPTIONS, Settings
from .notify import notify_all
from .output import read_json


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wypad")
    sub = p.add_subparsers(dest="cmd", required=True)
    ps = sub.add_parser("search", help="wyszukaj dzisiejsze okazje i zapisz pliki strony")
    ps.add_argument("--site", type=Path, required=True)
    ps.add_argument("--state", type=Path, required=True)
    ps.add_argument("--max-hotel-searches", type=int, default=None)
    ps.add_argument("--skip-if-done", action="store_true", help="nic nie rób, jeśli dane z dziś już są w --site")
    ps.add_argument("--force", action="store_true", help="szukaj od nowa (domyślne zachowanie; flaga dla czytelności workflow)")
    pn = sub.add_parser("notify", help="wyślij push i e-mail z dzisiejszymi okazjami")
    pn.add_argument("--site", type=Path, required=True)
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.cmd == "search":
        from .run import WARSAW, search
        if args.skip_if_done and not args.force:
            current = read_json(args.site / "data" / "deals.json") or {}
            today = datetime.now(WARSAW).date().isoformat()
            if current.get("date") == today and not current.get("sample"):
                print(f"Dane z {today} już są — pomijam wyszukiwanie.")
                return 0
        s = Settings()
        if args.max_hotel_searches:
            s.max_hotel_searches = args.max_hotel_searches
        try:
            payload = search(args.site, args.state, s)
        except RuntimeError as e:
            logging.error("%s", e)
            return 2
        print(f"OK: {len(payload['deals'])} okazji, {payload['stats']['flight_options']} kombinacji lotów, "
              f"{payload['stats']['duration_s']} s")
        return 0

    data = read_json(args.site / "data" / "deals.json")
    if not data or data.get("sample"):
        print("Brak prawdziwych danych — nie wysyłam powiadomień.")
        return 0
    s = Settings()
    bag = data.get("defaults", {}).get("bag", s.default_bag)
    label = f"{data['date'][8:10]}.{data['date'][5:7]}"
    res = notify_all(data["deals"], site_url=s.site_url, bag=bag, bag_label=BAG_OPTIONS[bag]["short"], date_label=label)
    print("Powiadomienia:", res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
