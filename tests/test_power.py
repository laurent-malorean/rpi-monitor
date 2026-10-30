import time

from rpimon.collectors import LinuxSensors, parse_pmic_power
from rpimon.monitor import Monitor

SAMPLE = """\
 VDD_CORE_A current(7)=0.50000000A
 1V8_SYS_A current(2)=1.00000000A
 3V3_NOVOLT_A current(3)=9.00000000A
 VDD_CORE_V volt(15)=2.00000000V
 1V8_SYS_V volt(10)=1.00000000V
 EXT5V_V volt(24)=4.90000000V
"""


def test_parse_pmic_power_sums_rails_with_current_and_voltage():
    # 0.5*2.0 + 1.0*1.0 ; EXT5V (sans courant) et rail sans tension ignorés
    assert parse_pmic_power(SAMPLE) == 2.0


def test_parse_pmic_power_unusable_output_is_none():
    assert parse_pmic_power("") is None
    assert parse_pmic_power("n'importe quoi") is None


def test_sensors_power_unavailable_is_none(tmp_path):
    assert LinuxSensors(tmp_path).power_w() is None


class FakeSensors:
    def cpu_percent(self): return 1.0
    def temperature_c(self): return 40.0
    def cpu_freq_mhz(self): return 1500.0
    def ram_percent(self): return 10.0
    def fan(self): raise OSError
    def power_w(self): return 3.5


def test_monitor_records_power():
    m = Monitor(sensors=FakeSensors())
    m.start(); time.sleep(0.7); m.stop()
    assert m.snapshot("power")[1] == 3.5
