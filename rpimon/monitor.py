"""Thread de collecte + historiques. Indépendant de l'affichage."""
from __future__ import annotations

import threading
import time

from .collectors import DemoSensors, LinuxSensors, parse_throttled
from .history import BucketSeries, RingBuffer

HISTORY_S = 30 * 60
FAST_S = 0.5  # ventilateur
SLOW_EVERY = 2  # autres métriques : 1 s


class Monitor:
    def __init__(self, sensors=None, demo: bool = False):
        self.sensors = sensors or (DemoSensors() if demo else LinuxSensors())
        self.series = {
            "cpu": RingBuffer(HISTORY_S),
            "temp": RingBuffer(HISTORY_S),
            "freq": RingBuffer(HISTORY_S),
            "ram": RingBuffer(HISTORY_S),
            "fan": BucketSeries(bucket_s=10, maxlen=HISTORY_S // 10),
            "throttle": BucketSeries(bucket_s=10, maxlen=HISTORY_S // 10),
        }
        self.fan_last = None
        self.throttle_last = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="collector", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def reset(self) -> None:
        with self._lock:
            for s in self.series.values():
                s.clear()

    def snapshot(self, key: str) -> tuple[list[float], object, object]:
        """(valeurs, dernière valeur, stats) copiés sous verrou."""
        with self._lock:
            s = self.series[key]
            return s.values(), s.last(), s.stats()

    def _safe(self, fn):
        try:
            return fn()
        except Exception:
            return None  # un capteur en panne ne doit jamais tuer la collecte

    def _run(self) -> None:
        tick = 0
        next_t = time.monotonic()
        while not self._stop.is_set():
            now = time.time()
            fan = self._safe(self.sensors.fan)
            with self._lock:
                self.fan_last = fan
                self.series["fan"].add(now, fan.active if fan else None)
            if tick % SLOW_EVERY == 0:
                vals = {
                    "cpu": self._safe(self.sensors.cpu_percent),
                    "temp": self._safe(self.sensors.temperature_c),
                    "freq": self._safe(self.sensors.cpu_freq_mhz),
                    "ram": self._safe(self.sensors.ram_percent),
                }
                raw = self._safe(getattr(self.sensors, "throttled", lambda: None))
                thr = None if raw is None else parse_throttled(raw)
                with self._lock:
                    for k, v in vals.items():
                        self.series[k].add(v)
                    self.throttle_last = thr
                    self.series["throttle"].add(now, None if thr is None else thr.active)
            tick += 1
            next_t += FAST_S
            self._stop.wait(max(0.0, next_t - time.monotonic()))
