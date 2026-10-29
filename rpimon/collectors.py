"""Collecteurs : lecture seule, indépendants de l'UI. Retour None si indisponible."""
from __future__ import annotations

import math
import random
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil

SYS = Path("/sys")


@dataclass(frozen=True)
class FanReading:
    state: int | None  # niveau demandé par le système (cooling_device cur_state)
    pwm: int | None  # consigne PWM 0..255
    rpm: int | None  # vitesse mesurée

    @property
    def active(self) -> bool | None:
        vals = [v for v in (self.state, self.pwm, self.rpm) if v is not None]
        if not vals:
            return None
        return any(v > 0 for v in vals)


_NOW_FLAGS = {0: "sous-tension", 1: "fréq. bridée", 2: "throttle", 3: "limite temp"}
_PAST_SHIFT = 16  # bits 16..19 : même événement, survenu depuis le boot


@dataclass(frozen=True)
class Throttle:
    now: tuple[str, ...]  # en cours
    since_boot: tuple[str, ...]  # survenus depuis le démarrage

    @property
    def active(self) -> bool:
        return bool(self.now)


def parse_throttled(raw: int) -> Throttle:
    """Décode le registre `get_throttled` du firmware Pi."""
    now = tuple(n for b, n in _NOW_FLAGS.items() if raw >> b & 1)
    past = tuple(n for b, n in _NOW_FLAGS.items() if raw >> (b + _PAST_SHIFT) & 1)
    return Throttle(now, past)


def _read_int(path: Path | None) -> int | None:
    if path is None:
        return None
    try:
        return int(path.read_text().strip())
    except (OSError, ValueError):
        return None


def _read_str(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def find_hwmon(name: str, root: Path = SYS / "class/hwmon") -> Path | None:
    """Chemin hwmon dont le fichier `name` vaut `name` (numérotation non fixe)."""
    for d in sorted(root.glob("hwmon*")):
        if _read_str(d / "name") == name:
            return d
    return None


def find_cooling_device(kind: str = "pwm-fan", root: Path = SYS / "class/thermal") -> Path | None:
    for d in sorted(root.glob("cooling_device*")):
        if _read_str(d / "type") == kind:
            return d
    return None


class LinuxSensors:
    """Capteurs Pi ; les chemins sont redétectés si une lecture échoue."""

    def __init__(self, sys_root: Path = SYS):
        self.root = sys_root
        self._fan_hwmon: Path | None = None
        self._cooling: Path | None = None
        self._temp_hwmon: Path | None = None
        self._throttle_file: Path | None = None
        self.detect()
        psutil.cpu_percent(interval=None)  # amorce : le 1er appel ne vaut rien

    def detect(self) -> None:
        self._fan_hwmon = find_hwmon("pwmfan", self.root / "class/hwmon")
        self._temp_hwmon = find_hwmon("cpu_thermal", self.root / "class/hwmon")
        self._cooling = find_cooling_device("pwm-fan", self.root / "class/thermal")
        plat = self.root / "devices/platform"
        self._throttle_file = next(
            iter([*plat.glob("*/get_throttled"), *plat.glob("*/*/get_throttled")]), None)

    def cpu_percent(self) -> float | None:
        try:
            return psutil.cpu_percent(interval=None)
        except Exception:
            return None

    def cpu_freq_mhz(self) -> float | None:
        try:
            f = psutil.cpu_freq()
            return f.current if f and f.current else None
        except Exception:
            return None

    def ram_percent(self) -> float | None:
        try:
            return psutil.virtual_memory().percent
        except Exception:
            return None

    def temperature_c(self) -> float | None:
        v = _read_int(self.root / "class/thermal/thermal_zone0/temp")
        if v is None and self._temp_hwmon:
            v = _read_int(self._temp_hwmon / "temp1_input")
        return None if v is None else v / 1000.0

    def throttled(self) -> int | None:
        raw = _read_str(self._throttle_file) if self._throttle_file else None
        if raw is None and self.root == SYS and shutil.which("vcgencmd"):
            try:  # lecture seule, sans sudo
                out = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                                     text=True, timeout=2).stdout
                raw = out.split("=")[-1].strip()
            except (OSError, subprocess.SubprocessError):
                return None
        try:
            return None if raw is None else int(raw, 0)
        except ValueError:
            return int(raw, 16) if raw else None

    def fan(self) -> FanReading:
        h = self._fan_hwmon
        r = FanReading(
            state=_read_int(self._cooling / "cur_state" if self._cooling else None),
            pwm=_read_int(h / "pwm1" if h else None),
            rpm=_read_int(h / "fan1_input" if h else None),
        )
        if h is None or (r.pwm is None and r.rpm is None):
            self.detect()  # périphérique disparu ou renuméroté
        return r


class DemoSensors:
    """Données synthétiques pour développer hors Raspberry Pi."""

    def __init__(self):
        self._cpu = 20.0
        self._temp = 45.0
        self._ram = 30.0

    def detect(self) -> None:
        pass

    def cpu_percent(self) -> float:
        self._cpu = min(100, max(0, self._cpu + random.uniform(-15, 15)))
        return self._cpu

    def cpu_freq_mhz(self) -> float:
        return 1500 + 900 * (self._cpu / 100) + random.uniform(-30, 30)

    def ram_percent(self) -> float:
        self._ram = min(95, max(5, self._ram + random.uniform(-1, 1)))
        return self._ram

    def temperature_c(self) -> float:
        target = 38 + 0.45 * self._cpu
        self._temp += (target - self._temp) * 0.05 + random.uniform(-0.3, 0.3)
        return self._temp

    def throttled(self) -> int:
        return 0x8 if self._temp > 54 else 0

    def fan(self) -> FanReading:
        on = self._temp > 52 or math.isclose(self._temp, 52, abs_tol=0.5)
        return FanReading(state=1 if on else 0, pwm=75 if on else 0, rpm=1700 if on else 0)
