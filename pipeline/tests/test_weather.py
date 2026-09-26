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
    def __init__(self):
        self.urls = []

    def get(self, url, timeout, params):
        self.urls.append(url)

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"daily": {"time": ["2025-10-20"] * 3, "temperature_2m_max": [15, 16, 17],
                                  "precipitation_sum": [0, 0, 0], "weather_code": [0, 0, 0]}}
        return R()


def test_forecast_for_near_trips_climate_for_far_ones_and_one_archive_call_per_city():
    weather._ARCHIVE.clear()
    s = FakeSession()
    today = date(2026, 9, 25)
    assert trip_weather(1.0, 2.0, date(2026, 10, 1), date(2026, 10, 4), today, session=s)["kind"] == "forecast"
    trip_weather(1.0, 2.0, date(2026, 10, 20), date(2026, 10, 22), today, session=s)
    trip_weather(1.0, 2.0, date(2026, 10, 19), date(2026, 10, 21), today, session=s)
    assert s.urls == ["https://api.open-meteo.com/v1/forecast", "https://archive-api.open-meteo.com/v1/archive"]


def test_weather_errors_are_swallowed():
    class Boom:
        def get(self, *a, **k):
            raise OSError("timeout")
    assert trip_weather(1.0, 2.0, date(2026, 10, 1), date(2026, 10, 4), date(2026, 9, 25), session=Boom()) is None
