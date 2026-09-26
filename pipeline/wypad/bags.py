"""Baggage add-on ESTIMATES for 2 adults, round trip (2 flights).

Exact Ryanair bag prices need the booking `availability` API, which requires sending `ToUs=AGREED`
(accepting Ryanair's terms on the user's behalf). Artur declined that on 2026-09-25, so prices are
estimated from Ryanair's official fees table and always labelled as estimates in the app.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# EUR per person per flight when added at booking. Source: Ryanair fees table (EN), checked 2026-09-25:
# https://www.ryanair.com/ie/en/useful-info/help-centre/fees
FEES_EUR = {
    "priority": (12.49, 36.00),   # Priority & 2 Cabin Bags (10 kg cabin bag)
    "checked20": (21.49, 59.99),  # 20 kg check-in bag
}
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


def estimator(rate: float, rate_label: str):
    """Returns estimate(combo) → {"small", "cabin10", "checked20"} with totals for 2 adults, both flights.
    Uses the middle of the fee range; the verified Regular-bundle prices on POZ routes (≈95–116 zł per
    person per flight, incl. a seat) sit close to it, so the estimate is realistic rather than a floor."""
    p_lo, p_hi = FEES_EUR["priority"]
    c_lo, c_hi = FEES_EUR["checked20"]
    priority = round((p_lo + p_hi) / 2 * rate)
    checked = round((c_lo + c_hi) / 2 * rate)
    fx = f"{rate_label}: 1 € = {rate:.2f} zł".replace(".", ",")
    result = {
        "small": {"total": 0, "estimated": False,
                  "note": "Każda osoba: mały bagaż pod siedzenie (40×30×20 cm). Jest w cenie biletu."},
        "cabin10": {"total": 2 * 2 * priority, "estimated": True, "per_unit": priority,
                    "basis": (f"Szacunek: środek cennika Ryanair za Priority i walizkę kabinową 10 kg "
                              f"({_fmt_eur(p_lo)}–{_fmt_eur(p_hi)} € za osobę za lot), czyli ok. {priority} zł "
                              f"× 2 osoby × 2 loty ({fx})."),
                    "note": "Każda osoba: mały bagaż pod siedzenie + walizka kabinowa 10 kg (Priority & 2 Cabin Bags)."},
        "checked20": {"total": 2 * checked, "estimated": True, "per_unit": checked,
                      "basis": (f"Szacunek: środek cennika Ryanair za walizkę rejestrowaną 20 kg "
                                f"({_fmt_eur(c_lo)}–{_fmt_eur(c_hi)} € za lot), czyli ok. {checked} zł × 2 loty, "
                                f"jedna walizka na 2 osoby ({fx})."),
                      "note": "Każda osoba: mały bagaż pod siedzenie + jedna wspólna walizka rejestrowana 20 kg na dwie osoby."},
    }
    return lambda combo: result
