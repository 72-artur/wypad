import json
from datetime import date

from wypad.weather import Weather, build_climate, climate_summary, describe, monthly_climate, summarize_forecast

TODAY = date(2026, 9, 25)


def test_describe_and_forecast_summary():
    assert describe(0) == ("słonecznie", "sun") and describe(63)[0] == "deszcz" and describe(999)[0] == "zmiennie"
    s = summarize_forecast({"temperature_2m_max": [20, 22, 24], "weather_code": [1, 1, 3], "precipitation_probability_max": [10, 70, 20]})
    assert s == {"kind": "forecast", "t_max": 22, "text": "prognoza: przeważnie słonecznie, możliwy deszcz", "icon": "sun"}
    assert summarize_forecast({"temperature_2m_max": []}) is None


def test_monthly_climate_needs_20_days_and_counts_wet_days():
    days = [f"2025-11-{d:02d}" for d in range(1, 31)] + [f"2025-12-{d:02d}" for d in range(1, 11)]
    daily = {"time": days, "temperature_2m_max": [15] * 20 + [17] * 10 + [5] * 10,
             "precipitation_sum": [0] * 15 + [2.0] * 15 + [0] * 10}
    assert monthly_climate(daily) == {"11": {"t_max": 16, "wet_pct": 50}}          # December has only 10 days
    assert climate_summary({"t_max": 16, "wet_pct": 50}) == {
        "kind": "climate", "t_max": 16, "text": "średnio o tej porze, deszcz w 50% dni", "icon": "cloud-rain"}


class FakeSession:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def get(self, url, timeout, params):
        self.calls.append((url, params.get("start_date"), params.get("end_date")))
        fail = self.fail

        class R:
            def raise_for_status(self):
                if fail:
                    raise OSError("read timed out")

            def json(self):
                return {"daily": {"time": [f"2025-10-{d:02d}" for d in range(1, 31)], "temperature_2m_max": [20] * 30,
                                  "precipitation_sum": [0] * 30, "weather_code": [0] * 30,
                                  "precipitation_probability_max": [0] * 30}}
        return R()


def test_near_trips_use_the_forecast():
    s = FakeSession()
    w = Weather(None, session=s).trip("barcelona", 1.0, 2.0, date(2026, 10, 1), date(2026, 10, 4), TODAY)
    assert w["kind"] == "forecast" and [c[0] for c in s.calls] == ["https://api.open-meteo.com/v1/forecast"]


def test_cached_climate_needs_no_network(tmp_path):
    (tmp_path / "climate.json").write_text(json.dumps({"barcelona": {"10": {"t_max": 22, "wet_pct": 20}}}))
    s = FakeSession(fail=True)
    w = Weather(tmp_path, session=s).trip("barcelona", 1.0, 2.0, date(2026, 10, 20), date(2026, 10, 23), TODAY)
    assert w["t_max"] == 22 and s.calls == []


def test_missing_city_is_fetched_once_and_saved(tmp_path):
    s = FakeSession()
    wx = Weather(tmp_path, session=s)
    assert wx.trip("rzym", 1.0, 2.0, date(2026, 10, 20), date(2026, 10, 23), TODAY)["t_max"] == 20
    wx.trip("rzym", 1.0, 2.0, date(2026, 10, 27), date(2026, 10, 30), TODAY)          # same city: from cache
    assert [c[1:] for c in s.calls] == [("2023-01-01", "2025-12-31")]
    wx.save()
    assert json.loads((tmp_path / "climate.json").read_text())["rzym"]["10"]["t_max"] == 20


def test_archive_budget_stops_slow_lookups():
    clock = iter([0, 100, 100, 100, 100]).__next__        # budget already spent at the first lookup
    s = FakeSession()
    wx = Weather(None, session=s, archive_budget_s=60, clock=clock)
    assert wx.trip("praga", 1.0, 2.0, date(2026, 10, 20), date(2026, 10, 23), TODAY) is None
    assert s.calls == []


def test_failures_are_not_retried_in_the_same_run():
    s = FakeSession(fail=True)
    wx = Weather(None, session=s)
    assert wx.trip("porto", 1.0, 2.0, date(2026, 10, 20), date(2026, 10, 23), TODAY) is None
    assert wx.trip("porto", 1.0, 2.0, date(2026, 11, 20), date(2026, 11, 23), TODAY) is None
    assert len(s.calls) == 1


def test_build_climate_skips_cached_cities(tmp_path):
    (tmp_path / "climate.json").write_text(json.dumps({"a": {"01": {"t_max": 1, "wet_pct": 1}}}))
    cities = {"a": ("A", "X", "XX", 1.0, 2.0, 100, ""), "b": ("B", "X", "XX", 3.0, 4.0, 100, "")}
    s = FakeSession()
    cache = build_climate(tmp_path, cities, TODAY, session=s, pause_s=0)
    assert set(cache) == {"a", "b"} and len(s.calls) == 1
