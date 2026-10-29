"""Dashboard TUI de monitoring Raspberry Pi 5 (lecture seule).

Lancement : uv run python app.py [--demo]
"""
from __future__ import annotations

import argparse
import sys

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from rpimon.monitor import Monitor
from rpimon.widgets import Lane, Spec, throttle_summary

SPECS = [
    Spec("cpu", "CPU", "%", "green", decimals=0, fixed=(0, 100)),
    Spec("temp", "Température", "°C", "red", decimals=1, min_span=10),
    Spec("freq", "Fréquence", "MHz", "cyan", decimals=0, min_span=400),
    Spec("throttle", "Throttling", "flags", "bright_red", bars=True, fixed=(0, 1),
         step_s=10.0, compact=True),
    Spec("ram", "RAM", "%", "magenta", decimals=1, fixed=(0, 100)),
    Spec("fan", "Ventilateur", "tr/min", "yellow", bars=True, fixed=(0, 1), step_s=10.0),
]


def fmt(v: float | None, d: int) -> str:
    return "--" if v is None else f"{v:.{d}f}"


class MonitorApp(App):
    TITLE = "RPi Monitor"
    CSS = "Screen { overflow: hidden; }"
    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("p", "toggle_pause", "Pause"),
        ("r", "reset", "Reset"),
        ("w", "cycle_window", "Fenêtre"),
    ]
    WINDOWS = [60.0, 300.0, 1800.0]

    def __init__(self, monitor: Monitor, demo: bool):
        super().__init__()
        self.monitor = monitor
        self.paused = False
        self.demo = demo
        self.window_idx = 1  # 5 min
        self._set_subtitle()

    def _set_subtitle(self) -> None:
        parts = ["DEMO"] if self.demo else []
        parts.append(f"fenêtre {int(self.WINDOWS[self.window_idx] // 60)} min")
        if self.paused:
            parts.append("PAUSE (collecte active)")
        self.sub_title = " · ".join(parts)

    def compose(self) -> ComposeResult:
        yield Header()
        for spec in SPECS:
            yield Lane(spec)
        yield Footer()

    def on_mount(self) -> None:
        self.monitor.start()
        self.set_interval(1.0, self.refresh_lanes)
        self.refresh_lanes()

    def on_unmount(self) -> None:
        self.monitor.stop()

    def refresh_lanes(self) -> None:
        if self.paused:
            return
        for lane in self.query(Lane):
            sp = lane.spec
            values, last, st = self.monitor.snapshot(sp.key)
            if sp.key == "throttle":
                thr = self.monitor.throttle_last
                big = "--" if thr is None else str(len(thr.now))
                stats = throttle_summary(thr)
            elif sp.bars:
                fan = self.monitor.fan_last
                rpm = fan.rpm if fan else None
                state = "ON" if fan and fan.active else "OFF" if fan and fan.active is not None else "N/A"
                big = fmt(rpm, 0)
                stats = f"{state} état {fmt(fan.state if fan else None, 0)} pwm {fmt(fan.pwm if fan else None, 0)}"
                stats += f" · actif {st.mean * 100:.0f}%" if st else ""
            else:
                big = fmt(last, sp.decimals)
                stats = (f"min {fmt(st.minimum, sp.decimals)} max {fmt(st.maximum, sp.decimals)} "
                         f"moy {fmt(st.mean, sp.decimals)}") if st else "N/A"
            lane.update_data(values, big, stats, self.WINDOWS[self.window_idx])

    def action_toggle_pause(self) -> None:
        self.paused = not self.paused
        self._set_subtitle()
        if not self.paused:
            self.refresh_lanes()

    def action_cycle_window(self) -> None:
        self.window_idx = (self.window_idx + 1) % len(self.WINDOWS)
        self._set_subtitle()
        was, self.paused = self.paused, False
        self.refresh_lanes()
        self.paused = was

    def action_reset(self) -> None:
        self.monitor.reset()
        self.refresh_lanes()


def main() -> None:
    ap = argparse.ArgumentParser(description="Moniteur Raspberry Pi (lecture seule)")
    ap.add_argument("--demo", action="store_true", help="données synthétiques")
    args = ap.parse_args()
    demo = args.demo or not sys.platform.startswith("linux")
    MonitorApp(Monitor(demo=demo), demo).run()


if __name__ == "__main__":
    main()
