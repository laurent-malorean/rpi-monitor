from rpimon.collectors import LinuxSensors, parse_throttled
from rpimon.monitor import Monitor


def test_parse_throttled_ok():
    t = parse_throttled(0)
    assert t.now == () and t.since_boot == () and t.active is False


def test_parse_throttled_now_and_since_boot():
    # 0x50005 : sous-tension + throttle en cours, déjà survenus depuis le boot
    t = parse_throttled(0x50005)
    assert t.now == ("sous-tension", "throttle")
    assert t.since_boot == ("sous-tension", "throttle")
    assert t.active is True


def test_parse_throttled_past_only_is_not_active():
    t = parse_throttled(0x80000)  # limite de température survenue, plus en cours
    assert t.now == () and t.since_boot == ("limite temp",) and t.active is False


def test_sensors_read_throttled_from_sysfs(tmp_path):
    f = tmp_path / "devices/platform/soc/soc:firmware/get_throttled"
    f.parent.mkdir(parents=True)
    f.write_text("0x50005\n")
    assert LinuxSensors(tmp_path).throttled() == 0x50005


def test_sensors_throttled_unavailable_is_none(tmp_path):
    assert LinuxSensors(tmp_path).throttled() is None


class FakeSensors:
    def __init__(self, raw):
        self.raw = raw
    def cpu_percent(self): return 1.0
    def temperature_c(self): return 40.0
    def cpu_freq_mhz(self): return 1500.0
    def ram_percent(self): return 10.0
    def fan(self): raise OSError
    def throttled(self): return self.raw


def test_monitor_records_throttle_activity():
    import time
    m = Monitor(sensors=FakeSensors(0x4))
    m.start(); time.sleep(0.7); m.stop()
    assert m.snapshot("throttle")[1] == 1.0
    assert m.throttle_last.now == ("throttle",)


def test_monitor_without_throttle_support_does_not_crash():
    import time
    s = FakeSensors(None)
    m = Monitor(sensors=s)
    m.start(); time.sleep(0.7); m.stop()
    assert m.snapshot("throttle")[1] is None
    assert m.throttle_last is None


def test_throttle_summary_texts():
    from rpimon.widgets import throttle_summary
    assert throttle_summary(None) == "N/A"
    assert throttle_summary(parse_throttled(0)) == "OK"
    assert throttle_summary(parse_throttled(0x4)) == "throttle"
    assert throttle_summary(parse_throttled(0x5)) == "sous-tension+throttle"
    assert throttle_summary(parse_throttled(0x80000)) == "OK (déjà: limite temp)"
