from wypad.bags import FALLBACK_EUR_PLN, estimator, eur_pln


class FakeHttp:
    def __init__(self, payload=None, fail=False):
        self.payload, self.fail = payload, fail

    def get_json(self, url, params=None, **kw):
        if self.fail:
            raise RuntimeError("down")
        return self.payload


def test_estimates_use_the_middle_of_the_official_fee_range():
    b = estimator(4.25, "kurs NBP")({})
    # Priority & 2 cabin bags: (12.49 + 36.00) / 2 = 24.245 € → 103 zł per person per flight
    assert b["cabin10"]["per_unit"] == 103 and b["cabin10"]["total"] == 103 * 2 * 2
    # 20 kg check-in: (21.49 + 59.99) / 2 = 40.74 € → 173 zł per flight, one bag shared by 2 people
    assert b["checked20"]["per_unit"] == 173 and b["checked20"]["total"] == 173 * 2
    assert b["small"] == {"total": 0, "estimated": False, "note": b["small"]["note"]}
    assert b["cabin10"]["estimated"] and b["checked20"]["estimated"]
    assert "12,49–36 €" in b["cabin10"]["basis"] and "1 € = 4,25 zł" in b["cabin10"]["basis"]
    assert "21,49–59,99 €" in b["checked20"]["basis"]


def test_nbp_rate_and_fallback():
    rate, label = eur_pln(FakeHttp({"rates": [{"mid": 4.2711, "effectiveDate": "2026-09-25"}]}))
    assert rate == 4.2711 and label == "kurs NBP z 2026-09-25"
    assert eur_pln(FakeHttp(fail=True)) == (FALLBACK_EUR_PLN, "kurs przybliżony")
