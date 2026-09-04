#!/usr/bin/env python3
"""Build a no-prep S x R matrix with retained atomic-result fanout."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "shdump"))

import agxparse  # noqa: E402


SOURCE = HERE / "work" / "native_archives" / "atomic_pending_fanout.bin"
OUTPUT = HERE / "work" / "pending_atomic_fanout"
LOAD_TOKENS = {1: 0x1100, 2: 0x5100, 3: 0x9100,
               4: 0xD100, 5: 0x1101, 6: 0x5101}
PUBLICATION_CODES = {1: 2, 2: 4, 3: 3, 4: 5, 5: 6, 6: 1}
DEAD_MOVES = bytes((0xAC, 1, 0xBC, 2, 0xCC, 3, 0xDC, 4, 0xEC, 5))


def dependency_bytes(original_b1: int, original_b2: int, slot: int):
    mask = 1 << (slot - 1)
    return ((original_b1 & 0x0F) | ((mask & 0x0F) << 4),
            (original_b2 & 0xFC) | ((mask >> 4) & 0x03))


def main() -> int:
    blob = bytearray(SOURCE.read_bytes())
    main_offset, main_size = agxparse.locate_region(
        bytes(blob), "_agc.main", stage="compute"
    )
    main = bytes(blob[main_offset:main_offset + main_size])
    expected = {
        0x04: bytes.fromhex("6710540402002000510100404600"),
        0x12: bytes.fromhex("0b000600200000140000"),
        0x1C: bytes.fromhex("6701560000010180000200007e02"),
        0x2A: bytes.fromhex("6c8019a500200000"),
        0x46: bytes.fromhex("9f015608021830a81501"),
    }
    for offset, pattern in expected.items():
        if main[offset:offset + len(pattern)] != pattern:
            raise ValueError(f"unexpected carrier bytes at main+{offset:#x}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for input_slot in range(1, 7):
        for result_slot in range(1, 7):
            archive = bytearray(blob)
            token = LOAD_TOKENS[input_slot]
            archive[main_offset + 0x0C] = token >> 8
            archive[main_offset + 0x0D] = token & 0xFF
            archive[main_offset + 0x12:main_offset + 0x1C] = DEAD_MOVES
            b1, b2 = dependency_bytes(0x01, 0x56, input_slot)
            archive[main_offset + 0x1D] = b1
            archive[main_offset + 0x1E] = b2
            archive[main_offset + 0x2F] = PUBLICATION_CODES[result_slot] << 5
            b1, b2 = dependency_bytes(0x01, 0x56, result_slot)
            archive[main_offset + 0x47] = b1
            archive[main_offset + 0x48] = b2
            name = f"none_s{input_slot}_r{result_slot}.bin"
            (OUTPUT / name).write_bytes(archive)
            rows.append({"archive": name, "prep": "none",
                         "input_slot": input_slot,
                         "result_slot": result_slot})

    (OUTPUT / "manifest.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(rows)} variants to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
