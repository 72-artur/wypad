"""Baggage add-on ESTIMATES for 2 adults, round trip (2 flights), per carrier.

Exact Ryanair bag prices need the booking `availability` API, which requires sending `ToUs=AGREED`
(accepting Ryanair's terms on the user's behalf). Artur declined that on 2026-09-25. Wizz Air's
exact prices sit behind bot protection. So prices are estimated from each carrier's official fee
table and always labelled as estimates in the app.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# EUR per person per flight when added at booking (official fee tables, checked 2026-09-25):
# Ryanair https://www.ryanair.com/ie/en/useful-info/help-centre/fees
# Wizz Air https://www.wizzair.com/en-gb/information-and-services/prices-discounts/all-services-fees
FEES_EUR = {
    "FR": {"name": "Ryanair", "cabin": "Priority i walizkę kabinową 10 kg",
           "priority": (12.49, 36.00), "checked20": (21.49, 59.99)},
    "W6": {"name": "Wizz Air", "cabin": "WIZZ Priority z walizką kabinową 10 kg",
           "priority": (13.00, 57.50), "checked20": (0.00, 112.50), "checked20_peak": (2.00, 122.00)},
}
WIZZ_PEAK = ((12, 15), (1, 10))   # Wizz high season for bags: 15 Dec – 10 Jan
FALLBACK_EUR_PLN = 4.25


def eur_pln(http=None) -> tuple[float, str]:
    """EUR mid rate from the National Bank of Poland (free, no key); fallback constant if unavailable."""
    if http is not None:
        try:
            data = http.get_json("https://api.nbp.pl/api/exchangerates/rates/a/eur/", params={"format": "json"})
            rate = float(data["rates"][0]["mid"])
            return rate, f"kurs NBP z {data['rates'][0]['effectiveDate']}"
        except Exception as e:  # noqa: BLE001
            log.warning("NBP rate unavailable (%s), using %.2f", e, FALLBACK_EUR_PLN)
    return FALLBACK_EUR_PLN, "kurs przybliżony"


def _fmt_eur(x: float) -> str:
    return f"{x:.2f}".replace(".", ",").replace(",00", "")


def in_wizz_peak(d: str) -> bool:
    md = (int(d[5:7]), int(d[8:10]))
    return md >= WIZZ_PEAK[0] or md <= WIZZ_PEAK[1]


def _bags(code: str, out_peak: bool, back_peak: bool, rate: float, rate_label: str) -> dict:
    fees = FEES_EUR.get(code, FEES_EUR["FR"])
    p_lo, p_hi = fees["priority"]
    priority = round((p_lo + p_hi) / 2 * rate)

    def checked_leg(peak: bool) -> tuple[int, tuple[float, float]]:
        lo, hi = fees["checked20_peak"] if peak and "checked20_peak" in fees else fees["checked20"]
        return round((lo + hi) / 2 * rate), (lo, hi)

    (c_out, (c_lo, c_hi)), (c_back, _) = checked_leg(out_peak), checked_leg(back_peak)
    fx = f"{rate_label}: 1 € = {rate:.2f} zł".replace(".", ",")
    peak_legs = sum((out_peak, back_peak)) if "checked20_peak" in fees else 0
    season = f" ({peak_legs} z 2 lotów w szczycie świątecznym: {_fmt_eur(fees['checked20_peak'][0])}–{_fmt_eur(fees['checked20_peak'][1])} €)" if peak_legs else ""
    return {
        "small": {"total": 0, "estimated": False,
                  "note": "Każda osoba: mały bagaż pod siedzenie (40×30×20 cm). Jest w cenie biletu."},
        "cabin10": {"total": 2 * 2 * priority, "estimated": True, "per_unit": priority,
                    "basis": (f"Szacunek: środek cennika {fees['name']} za {fees['cabin']} "
                              f"({_fmt_eur(p_lo)}–{_fmt_eur(p_hi)} € za osobę za lot), czyli ok. {priority} zł "
                              f"× 2 osoby × 2 loty ({fx})."),
                    "note": f"Każda osoba: mały bagaż pod siedzenie + walizka kabinowa 10 kg ({'WIZZ Priority' if code == 'W6' else 'Priority & 2 Cabin Bags'})."},
        "checked20": {"total": c_out + c_back, "estimated": True, "per_unit": c_out,
                      "basis": (f"Szacunek: środek cennika {fees['name']} za walizkę rejestrowaną 20 kg "
                                f"({_fmt_eur(c_lo)}–{_fmt_eur(c_hi)} € za lot{season}), razem ok. {c_out + c_back} zł za 2 loty, "
                                f"jedna walizka na 2 osoby ({fx})."),
                      "note": "Każda osoba: mały bagaż pod siedzenie + jedna wspólna walizka rejestrowana 20 kg na dwie osoby."},
    }


def estimator(rate: float, rate_label: str):
    """Returns estimate(combo) → {"small", "cabin10", "checked20"} with totals for 2 adults, both flights,
    using the fee table of the combo's carrier. The middle of the range is used; for Ryanair the verified
    Regular-bundle prices on POZ routes (≈95–116 zł per person per flight, incl. a seat) sit close to it."""
    cache: dict[tuple, dict] = {}

    def estimate(combo: dict) -> dict:
        code = combo.get("carrier_code") or "FR"
        out_peak = code == "W6" and in_wizz_peak(combo["out_dep"])
        back_peak = code == "W6" and in_wizz_peak(combo["back_dep"])
        key = (code, out_peak, back_peak)
        if key not in cache:
            cache[key] = _bags(code, out_peak, back_peak, rate, rate_label)
        return cache[key]
    return estimate
