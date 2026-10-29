from rpimon.collectors import FanReading, LinuxSensors, find_hwmon
from rpimon.monitor import Monitor
from rpimon.widgets import auto_scale, render_rows


def make_sys(tmp_path, fan_n=2, pwm=75, rpm=1700, state=1):
    hw = tmp_path / "class/hwmon"
    for n, name in [(0, "cpu_thermal"), (fan_n, "pwmfan")]:
        d = hw / f"hwmon{n}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "name").write_text(name + "\n")
    fan = hw / f"hwmon{fan_n}"
    (fan / "pwm1").write_text(f"{pwm}\n")
    (fan / "fan1_input").write_text(f"{rpm}\n")
    cd = tmp_path / "class/thermal/cooling_device0"
    cd.mkdir(parents=True)
    (cd / "type").write_text("pwm-fan\n")
    (cd / "cur_state").write_text(f"{state}\n")
    tz = tmp_path / "class/thermal/thermal_zone0"
    tz.mkdir()
    (tz / "temp").write_text("48250\n")
    return tmp_path


def test_hwmon_detected_by_name_not_number(tmp_path):
    make_sys(tmp_path, fan_n=5)
    assert find_hwmon("pwmfan", tmp_path / "class/hwmon").name == "hwmon5"


def test_linux_sensors_read(tmp_path):
    s = LinuxSensors(make_sys(tmp_path))
    assert s.temperature_c() == 48.25
    f = s.fan()
    assert (f.state, f.pwm, f.rpm, f.active) == (1, 75, 1700, True)


def test_missing_sensors_do_not_crash(tmp_path):
    s = LinuxSensors(tmp_path)  # rien dans /sys
    assert s.temperature_c() is None
    f = s.fan()
    assert f.active is None


def test_fan_active_if_any_signal_positive():
    assert FanReading(0, 0, 0).active is False
    assert FanReading(1, 0, 0).active is True  # tourne alors que pwm/rpm = 0
    assert FanReading(None, None, None).active is None


def test_monitor_survives_failing_sensor():
    class Broken:
        def cpu_percent(self): raise OSError
        def temperature_c(self): return 40.0
        def cpu_freq_mhz(self): return None
        def ram_percent(self): return 10.0
        def fan(self): raise OSError
    m = Monitor(sensors=Broken())
    m.start()
    import time; time.sleep(0.7)
    m.stop()
    assert m.snapshot("temp")[1] == 40.0
    assert m.snapshot("cpu")[1] is None


def test_render_rows_shape_and_scale():
    rows = render_rows([0, 50, 100], width=5, height=2, lo=0, hi=100)
    assert len(rows) == 2 and all(len(r) == 5 for r in rows)
    assert rows[0][-1] == "█" and rows[1][-1] == "█"  # 100 % remplit tout


def test_temperature_scale_can_go_below_30():
    lo, hi = auto_scale([22.0, 25.0], min_span=10)
    assert lo < 22.0 and hi > 25.0


def test_resample_window_fills_width():
    from rpimon.widgets import resample
    out = resample([1.0, 3.0], n_points=4, width=4)
    assert len(out) == 4 and out[-1] == 3.0 and out[-2] == 1.0
    import math
    assert math.isnan(out[0])
    assert resample([0.0, 1.0, 0.0, 0.0], 4, 2, use_max=True) == [1.0, 0.0]


def test_render_line_is_a_curve_not_a_fill():
    from rpimon.widgets import render_line
    rows = render_line([10.0] * 8, width=4, height=2, lo=0, hi=100)
    assert len(rows) == 2 and all(len(r) == 4 for r in rows)
    assert rows[0].strip("⠀") == ""  # valeur basse : rien en haut
    rows = render_line([0.0, 100.0] + [float("nan")] * 6, width=4, height=2, lo=0, hi=100)
    assert rows[0][0] != "⠀" and rows[1][0] != "⠀"  # segment vertical relié
