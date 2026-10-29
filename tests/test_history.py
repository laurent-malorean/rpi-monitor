import math

from rpimon.history import BucketSeries, RingBuffer


def test_ring_buffer_is_bounded():
    rb = RingBuffer(3)
    for i in range(10):
        rb.add(i)
    assert rb.values() == [7, 8, 9]


def test_ring_buffer_stats_ignore_unavailable():
    rb = RingBuffer(10)
    for v in (10, None, 30):
        rb.add(v)
    s = rb.stats()
    assert (s.minimum, s.maximum, s.mean) == (10, 30, 20)
    assert RingBuffer(5).stats() is None


def test_ring_buffer_last_none_when_unavailable():
    rb = RingBuffer(5)
    rb.add(1)
    rb.add(None)
    assert rb.last() is None


def test_one_second_activation_is_kept_in_ten_second_bucket():
    b = BucketSeries(bucket_s=10)
    # 20 mesures à 500 ms sur 10 s, une seule seconde (2 mesures) active
    for i in range(20):
        b.add(100 + i * 0.5, active=(8 <= i < 10))
    b.add(110.0, False)  # ouvre la période suivante
    vals = b.values()
    assert vals[0] == 2 / 20 and vals[0] > 0
    assert vals[1] == 0


def test_inactive_bucket_is_zero():
    b = BucketSeries()
    for i in range(20):
        b.add(100 + i * 0.5, False)
    assert b.values() == [0.0]


def test_gap_periods_are_unavailable_not_zero():
    b = BucketSeries()
    b.add(100.0, True)
    b.add(135.0, True)
    vals = b.values()
    assert vals[0] == 1.0 and math.isnan(vals[1]) and math.isnan(vals[2])


def test_bucket_series_is_bounded_and_clear():
    b = BucketSeries(bucket_s=1, maxlen=5)
    for t in range(50):
        b.add(float(t), True)
    assert len(b.values()) <= 5
    b.clear()
    assert b.values() == []
