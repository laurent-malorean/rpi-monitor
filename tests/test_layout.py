import app


def test_indicators_display_order():
    assert [s.key for s in app.SPECS] == ["cpu", "freq", "power", "ram", "temp", "fan", "throttle"]
