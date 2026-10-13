import pytest

from stolenhours import live
from stolenhours.webgui import server


class StubBridge:
    def __init__(self):
        self.values = {"m_permanent.envInfo.gameTime": "2110.58", "m_permanent.WeatherInfo.weatherType": "1",
                       "m_permanent.envInfo.gameTimePeriodType": "EGameTimePeriodType::Day(0)"}
        self.sets = []

    def get(self, target, prop):
        return live.Reply(True, self.values[prop])

    def set(self, target, prop, value):
        self.sets.append((target, prop, value))
        return live.Reply(True, f"x -> {value}")


@pytest.fixture
def backend():
    b = server.Backend.__new__(server.Backend)
    b.bridge = StubBridge()
    return b


def test_get_clock(backend):
    r = backend.api_live("get_clock")
    assert r["ok"] and r["clock"]["time"] == "2110.58" and r["clock"]["period"].endswith("(0)")


def test_set_clock_validates(backend):
    assert backend.api_live("set_time", "1350")["ok"]
    assert backend.api_live("set_period", "1")["ok"]
    assert backend.api_live("set_weather", "2")["ok"]
    assert backend.bridge.sets == [("GDDPhaseStatus", "m_permanent.envInfo.gameTime", 1350.0),
                                   ("GDDPhaseStatus", "m_permanent.envInfo.gameTimePeriodType", 1),
                                   ("GDDWeatherStatus", "m_permanent.WeatherInfo.weatherType", 2)]
    for action, value in (("set_period", "2"), ("set_weather", "0"), ("set_time", "-5")):
        with pytest.raises(server.ApiError):
            backend.api_live(action, value)
