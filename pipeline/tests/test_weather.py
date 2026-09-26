from datetime import date

from wypad import weather
from wypad.weather import _same_season, describe, summarize_climate, summarize_forecast, trip_weather


def test_describe_and_forecast_summary():
    assert describe(0) == ("słonecznie", "sun") and describe(63)[0] == "deszcz" and describe(999)[0] == "zmiennie"
    s = summarize_forecast({"temperature_2m_max": [20, 22, 24], "weather_code": [1, 1, 3], "precipitation_probability_max": [10, 70, 20]})
    assert s == {"kind": "forecast", "t_max": 22, "text": "prognoza: przeważnie słonecznie, możliwy deszcz", "icon": "sun"}
    assert summarize_forecast({"temperature_2m_max": []}) is None


def test_climate_summary_uses_same_calendar_days_of_past_years():
    daily = {"time": ["2024-11-13", "2024-11-14", "2024-11-20", "2025-11-13", "2025-11-14"],
             "temperature_2m_max": [18, 20, 30, 19, 21], "precipitation_sum": [0, 2.0, 0, 0, 5.0]}
    s = summarize_climate(daily, date(2026, 11, 13), date(2026, 11, 16))
    assert s["t_max"] == 20 and "deszcz w 50% dni" in s["text"]     # the 20 Nov day is outside the window
    assert _same_season(date(2025, 1, 2), date(2026, 12, 30), date(2027, 1, 3))   # window across New Year


class FakeSession:
    def __init__(self, fail_years=()):
        self.calls, self.fail_years = [], set(fail_years)

    def get(self, url, timeout, params):
        self.calls.append((url, params.get("start_date"), params.get("end_date"), timeout))
        fail = params.get("start_date", "")[:4] in self.fail_years

        class R:
            def raise_for_status(self):
                if fail:
                    raise OSError("read timed out")

            def json(self):
                start = params["start_date"]
                return {"daily": {"time": [start, start], "temperature_2m_max": [15, 17],
                                  "precipitation_sum": [0, 3.0], "weather_code": [0, 0]}}
        return R()


def test_near_trips_use_the_forecast():
    weather._ARCHIVE.clear()
    s = FakeSession()
    w = trip_weather(1.0, 2.0, date(2026, 10, 1), date(2026, 10, 4), date(2026, 9, 25), session=s)
    assert w["kind"] == "forecast" and [c[0] for c in s.calls] == ["https://api.open-meteo.com/v1/forecast"]


def test_far_trips_use_small_windows_of_the_last_three_years_and_cache_them():
    weather._ARCHIVE.clear()
    s = FakeSession()
    today = date(2026, 9, 25)
    w = trip_weather(1.0, 2.0, date(2026, 10, 20), date(2026, 10, 22), today, session=s)
    assert w["kind"] == "climate" and w["t_max"] == 16 and "deszcz w 50% dni" in w["text"]
    assert [(c[1], c[2]) for c in s.calls] == [("2025-10-20", "2025-10-22"), ("2024-10-20", "2024-10-22"), ("2023-10-20", "2023-10-22")]
    assert all(c[3] == weather.ARCHIVE_TIMEOUT_S for c in s.calls)
    trip_weather(1.0, 2.0, date(2026, 10, 20), date(2026, 10, 22), today, session=s)   # same window → cached
    assert len(s.calls) == 3


def test_one_failed_year_still_gives_an_average_and_leap_day_is_safe():
    weather._ARCHIVE.clear()
    w = trip_weather(1.0, 2.0, date(2026, 10, 20), date(2026, 10, 22), date(2026, 9, 25), session=FakeSession(fail_years={"2024"}))
    assert w is not None and w["kind"] == "climate"
    assert weather._years_earlier(date(2028, 2, 29), 1) == date(2027, 2, 28)


def test_weather_errors_are_swallowed():
    class Boom:
        def get(self, *a, **k):
            raise OSError("timeout")
    assert trip_weather(1.0, 2.0, date(2026, 10, 1), date(2026, 10, 4), date(2026, 9, 25), session=Boom()) is None
