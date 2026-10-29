"""Rendu : fonction pure de tracé + widgets Textual."""
from __future__ import annotations

import math
from dataclasses import dataclass

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Digits, Static

BLOCKS = " ▁▂▃▄▅▆▇█"
AXIS_W = 6


@dataclass(frozen=True)
class Spec:
    key: str
    title: str
    unit: str
    color: str
    decimals: int = 1
    fixed: tuple[float, float] | None = None  # échelle fixe, sinon auto
    min_span: float = 10.0  # amplitude minimale en échelle auto
    bars: bool = False  # histogramme (ventilateur) plutôt que courbe
    step_s: float = 1.0  # pas d'échantillonnage des valeurs stockées


def auto_scale(values: list[float], min_span: float) -> tuple[float, float]:
    ok = [v for v in values if not math.isnan(v)]
    if not ok:
        return 0.0, min_span
    lo, hi = min(ok), max(ok)
    span = max(hi - lo, min_span)
    pad = span * 0.15
    mid = (hi + lo) / 2
    return mid - span / 2 - pad, mid + span / 2 + pad


def resample(values: list[float], n_points: int, width: int, use_max: bool = False) -> list[float]:
    """Ramène les `n_points` dernières valeurs sur `width` colonnes (moyenne ou max)."""
    pts = values[-n_points:]
    pts = [math.nan] * (n_points - len(pts)) + pts
    out = []
    for c in range(width):
        a = c * n_points // width
        b = max(a + 1, (c + 1) * n_points // width)
        ok = [v for v in pts[a:b] if not math.isnan(v)]
        out.append(math.nan if not ok else max(ok) if use_max else sum(ok) / len(ok))
    return out


def render_rows(values: list[float], width: int, height: int,
                lo: float, hi: float, min_level: int = 0) -> list[str]:
    """Tracé en blocs 1/8 : `height` lignes de `width` colonnes, plus récent à droite."""
    cols = values[-width:]
    cols = [math.nan] * (width - len(cols)) + cols
    span = (hi - lo) or 1.0
    levels = []
    for v in cols:
        if math.isnan(v):
            levels.append(0)
            continue
        lvl = round((v - lo) / span * height * 8)
        lvl = max(0, min(height * 8, lvl))
        if min_level and v > lo:
            lvl = max(lvl, min_level)  # une activation brève reste visible
        levels.append(lvl)
    rows = []
    for r in range(height - 1, -1, -1):
        rows.append("".join(BLOCKS[max(0, min(8, lv - r * 8))] for lv in levels))
    return rows


_LEFT = (0x01, 0x02, 0x04, 0x40)  # bits braille, colonne gauche, de haut en bas
_RIGHT = (0x08, 0x10, 0x20, 0x80)


def render_line(values: list[float], width: int, height: int, lo: float, hi: float) -> list[str]:
    """Courbe en braille (2x4 points par cellule). `values` : 2*width points."""
    dots_h = height * 4
    span = (hi - lo) or 1.0
    cells = [[0] * width for _ in range(height)]

    def mark(x: int, y: int) -> None:  # y = 0 en haut
        bits = _RIGHT if x % 2 else _LEFT
        cells[y // 4][x // 2] |= bits[y % 4]

    prev = None
    for x, v in enumerate(values[: width * 2]):
        if math.isnan(v):
            prev = None
            continue
        y = dots_h - 1 - max(0, min(dots_h - 1, round((v - lo) / span * (dots_h - 1))))
        for yy in range(min(y, prev), max(y, prev) + 1) if prev is not None else (y,):
            mark(x, yy)  # relie au point précédent : courbe continue
        prev = y
    return ["".join(chr(0x2800 + c) for c in row) for row in cells]


class Chart(Widget):
    DEFAULT_CSS = "Chart { width: 1fr; height: 1fr; }"

    def __init__(self, spec: Spec):
        super().__init__()
        self.spec = spec
        self.values: list[float] = []
        self.window_s: float = 300.0

    def render(self) -> Text:
        w, h = self.size
        if w <= AXIS_W + 2 or h < 2:
            return Text("")
        sp = self.spec
        n_points = max(1, int(self.window_s / sp.step_s))
        pw = w - AXIS_W
        cols = resample(self.values, n_points, pw if sp.bars else pw * 2, use_max=sp.bars)
        lo, hi = sp.fixed if sp.fixed else auto_scale(cols, sp.min_span)
        if sp.bars:
            rows = render_rows(cols, pw, h, lo, hi, min_level=3)
        else:
            rows = render_line(cols, pw, h, lo, hi)
        fmt = f"{{:{AXIS_W - 1}.{0 if sp.fixed or hi - lo > 20 else 1}f}}"
        out = Text(no_wrap=True, overflow="crop")
        for i, row in enumerate(rows):
            if sp.bars:
                label = "ON" if i == 0 else "OFF" if i == h - 1 else ""
            else:
                label = fmt.format(hi) if i == 0 else fmt.format(lo) if i == h - 1 else ""
            out.append(f"{label:>{AXIS_W - 1}} ", style="dim")
            out.append(row, style=sp.color)
            if i < h - 1:
                out.append("\n")
        return out


class Lane(Widget):
    """Une ligne : indicateur en gros à gauche, courbe temporelle à droite."""

    DEFAULT_CSS = """
    Lane { height: 1fr; border-top: solid $panel; }
    Lane .left { width: 30; padding: 0 1; }
    Lane .title { text-style: bold; }
    Lane Digits { height: 3; }
    Lane .stats { height: 1; color: $text-muted; }
    """

    def __init__(self, spec: Spec):
        super().__init__()
        self.spec = spec

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(classes="left"):
                yield Static(f"{self.spec.title} ({self.spec.unit})", classes="title")
                yield Digits("--", classes="big")
                yield Static("", classes="stats")
            yield Chart(self.spec)

    def update_data(self, values, big: str, stats: str, window_s: float) -> None:
        chart = self.query_one(Chart)
        chart.values = values
        chart.window_s = window_s
        chart.refresh()
        self.query_one(Digits).update(big)
        self.query_one(".stats", Static).update(stats)
