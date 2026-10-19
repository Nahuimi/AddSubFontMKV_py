"""UUEncode 编解码往返测试。"""

from __future__ import annotations

import random

from asfmkv.ass.embedded import decode_uue, encode_uue


def test_roundtrip_random_bytes():
    rng = random.Random(20240928)
    for size in (1, 2, 3, 4, 5, 63, 64, 65, 1000, 5000):
        data = bytes(rng.randrange(256) for _ in range(size))
        rows = encode_uue(data, "x.ttf", True)
        assert decode_uue(rows[:]) == data


def test_roundtrip_with_header():
    data = bytes(range(256)) * 4
    rows = encode_uue(data, "font.ttf", True)
    assert rows[0].startswith("fontname:")
    assert decode_uue(rows[:]) == data
