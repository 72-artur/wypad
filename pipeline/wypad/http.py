"""One polite HTTP session for the whole run: browser-like headers, retries with backoff, a pause between calls."""
from __future__ import annotations

import logging
import time

import requests

log = logging.getLogger(__name__)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")


class Http:
    def __init__(self, delay_s: float = 1.0, retries: int = 3):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*",
                               "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8"})
        self.delay_s = delay_s
        self.retries = retries
        self.calls = 0
        self._last = 0.0

    def _wait(self) -> None:
        gap = time.monotonic() - self._last
        if gap < self.delay_s:
            time.sleep(self.delay_s - gap)
        self._last = time.monotonic()

    def get_json(self, url: str, params: dict | None = None, **kw):
        last_err: Exception | None = None
        for attempt in range(self.retries):
            self._wait()
            self.calls += 1
            try:
                r = self.s.get(url, params=params, timeout=kw.pop("timeout", 30), **kw)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"HTTP {r.status_code}", response=r)
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
                backoff = 2 ** attempt * 3
                log.info("GET %s failed (%s), retry in %ss", url, e, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"GET {url} failed after {self.retries} attempts: {last_err}")
