"""Stockage de l'historique : buffers circulaires, sans dépendance à l'UI."""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


def _valid(values) -> list[float]:
    return [v for v in values if not math.isnan(v)]


@dataclass(frozen=True)
class Stats:
    minimum: float
    maximum: float
    mean: float


class RingBuffer:
    """Buffer circulaire de floats ; NaN = mesure indisponible."""

    def __init__(self, maxlen: int):
        self._data: deque[float] = deque(maxlen=maxlen)

    def __len__(self) -> int:
        return len(self._data)

    def add(self, value: float | None) -> None:
        self._data.append(math.nan if value is None else float(value))

    def values(self) -> list[float]:
        return list(self._data)

    def last(self) -> float | None:
        if not self._data or math.isnan(self._data[-1]):
            return None
        return self._data[-1]

    def stats(self) -> Stats | None:
        ok = _valid(self._data)
        if not ok:
            return None
        return Stats(min(ok), max(ok), sum(ok) / len(ok))

    def clear(self) -> None:
        self._data.clear()


class BucketSeries:
    """Agrège des mesures booléennes par périodes fixes (10 s par défaut).

    Chaque période vaut la fraction de mesures « actives » (0..1). Une seule
    activation suffit à rendre la valeur > 0 : la période n'est jamais perdue.
    """

    def __init__(self, bucket_s: float = 10.0, maxlen: int = 180):
        self.bucket_s = bucket_s
        self._done: deque[float] = deque(maxlen=maxlen)
        self._maxlen = maxlen
        self._bucket_id: int | None = None
        self._active = 0
        self._total = 0

    def _fraction(self) -> float:
        return self._active / self._total if self._total else math.nan

    def add(self, ts: float, active: bool | None) -> None:
        bid = int(ts // self.bucket_s)
        if self._bucket_id is None:
            self._bucket_id = bid
        elif bid > self._bucket_id:
            self._done.append(self._fraction())
            gap = min(bid - self._bucket_id - 1, self._maxlen)
            self._done.extend([math.nan] * gap)  # périodes sans mesure
            self._bucket_id = bid
            self._active = self._total = 0
        if active is None:
            return
        self._total += 1
        self._active += bool(active)

    def values(self) -> list[float]:
        """Périodes terminées + période en cours (dernier élément)."""
        out = list(self._done)
        if self._bucket_id is not None:
            out.append(self._fraction())
        return out[-self._maxlen:]

    def last(self) -> float | None:
        v = self.values()
        return None if not v or math.isnan(v[-1]) else v[-1]

    def stats(self) -> Stats | None:
        ok = _valid(self.values())
        if not ok:
            return None
        return Stats(min(ok), max(ok), sum(ok) / len(ok))

    def clear(self) -> None:
        self._done.clear()
        self._bucket_id = None
        self._active = self._total = 0
