"""Search parameters agreed with Artur on 2026-09-25 (see docs/WYMAGANIA.md)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

# Origin airports: Poznań first, then airports within ~2.5 h drive from Poznań.
ORIGINS: dict[str, dict] = {
    "POZ": {"city": "Poznań", "city_gen": "Poznania", "drive": None},
    "WRO": {"city": "Wrocław", "city_gen": "Wrocławia", "drive": "~2 h z Poznania"},
    "BZG": {"city": "Bydgoszcz", "city_gen": "Bydgoszczy", "drive": "~1 h 45 min z Poznania"},
    "SZZ": {"city": "Szczecin", "city_gen": "Szczecina", "drive": "~2 h 30 min z Poznania"},
    "LCJ": {"city": "Łódź", "city_gen": "Łodzi", "drive": "~2 h 30 min z Poznania"},
}

BAG_OPTIONS: dict[str, dict] = {
    "small": {"short": "Plecak", "phrase": "plecak", "long": "Każda osoba: mały bagaż pod siedzenie (40×30×20 cm)."},
    "cabin10": {"short": "10 kg", "phrase": "bagaż 10 kg", "long": "Każda osoba: mały bagaż pod siedzenie + walizka kabinowa 10 kg (Priority)."},
    "checked20": {"short": "Plecak + 20 kg", "phrase": "walizka 20 kg", "long": "Każda osoba: mały bagaż pod siedzenie + jedna walizka rejestrowana 20 kg na dwie osoby."},
}


@dataclass
class Settings:
    origins: tuple[str, ...] = tuple(ORIGINS)
    carriers: tuple[str, ...] = ("FR", "W6")   # Ryanair (required), Wizz Air (best effort)
    nights: tuple[int, ...] = (2, 3, 4)
    horizon_days: int = 56          # 8 weeks ahead
    min_lead_days: int = 1          # earliest departure: tomorrow
    last_minute_days: int = 21
    budget_pln: int = 2500          # default UI filter, total for 2 adults
    default_bag: str = "cabin10"
    adults: int = 2
    min_rating: float = 8.0         # guest rating on a 0–10 scale
    max_distance_km: float = 3.0    # from the city centre
    max_candidates_per_city: int = 2
    max_hotel_searches: int = 18    # per daily run
    max_deals: int = 18             # published per day (at most one per hotel search)
    archive_days: int = 60
    request_delay_s: float = 1.0
    site_url: str = field(default_factory=lambda: os.environ.get("WYPAD_SITE_URL", "").rstrip("/"))
