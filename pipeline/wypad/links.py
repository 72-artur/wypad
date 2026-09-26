"""Deep links that open third-party search pages with the deal's exact parameters."""
from __future__ import annotations

import base64
from urllib.parse import quote


def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _bytes_field(num: int, data: bytes) -> bytes:
    return _varint(num << 3 | 2) + _varint(len(data)) + data


def _varint_field(num: int, value: int) -> bytes:
    return _varint(num << 3) + _varint(value)


def _leg(day: str, frm: str, to: str) -> bytes:
    return (_bytes_field(2, day.encode()) + _bytes_field(13, _bytes_field(2, frm.encode()))
            + _bytes_field(14, _bytes_field(2, to.encode())))


def google_flights_tfs(origin: str, dest: str, out_date: str, back_date: str, adults: int = 2) -> str:
    """Google Flights `tfs` protobuf (same layout as the fast-flights library): two legs, N adults,
    economy, round trip. The natural-language `?q=` link is NOT used: it opened with 3 adults when asked
    for 2 (research 2026-09-25)."""
    msg = (_bytes_field(3, _leg(out_date, origin, dest)) + _bytes_field(3, _leg(back_date, dest, origin))
           + _bytes_field(8, bytes([1] * adults)) + _varint_field(9, 1) + _varint_field(19, 1))
    return base64.b64encode(msg).decode()


def google_flights_url(origin: str, dest: str, out_date: str, back_date: str, adults: int = 2) -> str:
    tfs = google_flights_tfs(origin, dest, out_date, back_date, adults)
    return f"https://www.google.com/travel/flights/search?tfs={quote(tfs, safe='=')}&hl=pl&curr=PLN"
