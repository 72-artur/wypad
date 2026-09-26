import json
from datetime import date

from wypad.history import load_fares, mark_changes, previous_payload, save_fares, typical_with_history

TODAY = date(2026, 9, 25)


def test_typical_blends_last_30_days_and_prunes(tmp_path):
    stored = {"POZ-BCN": {"2026-09-01": 400.0, "2026-09-20": 500.0, "2026-07-01": 50.0}}
    typ = typical_with_history({"POZ-BCN": 300.0, "POZ-LIS": 600.0}, stored, TODAY)
    assert typ == {"POZ-BCN": 400.0, "POZ-LIS": 600.0}   # July value is outside the 30-day window
    save_fares(tmp_path, stored, {"POZ-BCN": 300.0}, TODAY)
    saved = load_fares(tmp_path)
    assert saved["POZ-BCN"] == {"2026-09-01": 400.0, "2026-09-20": 500.0, "2026-09-25": 300.0}  # 2026-07-01 pruned (>45 days)


def test_previous_payload_picks_latest_day_before_today(tmp_path):
    arch = tmp_path / "data" / "archive"
    arch.mkdir(parents=True)
    for day in ("2026-09-22", "2026-09-24", "2026-09-25"):
        (arch / f"{day}.json").write_text(json.dumps({"date": day}))
    assert previous_payload(tmp_path, TODAY)["date"] == "2026-09-24"


def test_new_and_price_drop_badges():
    prev = {"deals": [{"id": "a", "totals": {"cabin10": 2000}}, {"id": "b", "totals": {"cabin10": 1500}}]}
    deals = [{"id": "a", "labels": [], "totals": {"cabin10": 1850}},   # cheaper by 150
             {"id": "b", "labels": [], "totals": {"cabin10": 1490}},   # only 10 zł: below threshold
             {"id": "c", "labels": [], "totals": {"cabin10": 999}}]    # new today
    mark_changes(deals, prev, "cabin10")
    assert deals[0].get("price_drop") == 150 and "new" not in deals[0]["labels"]
    assert deals[1].get("price_drop") is None
    assert deals[2]["labels"] == ["new"]


def test_sample_data_never_produces_badges():
    deals = [{"id": "x", "labels": [], "totals": {"cabin10": 1}}]
    mark_changes(deals, {"sample": True, "deals": []}, "cabin10")
    assert deals[0]["labels"] == []
