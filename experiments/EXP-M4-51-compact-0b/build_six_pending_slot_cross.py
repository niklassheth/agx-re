#!/usr/bin/env python3
"""Build every input-slot to native returned-atomic-slot permutation."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "shdump"))

import agxparse  # noqa: E402


SOURCE = HERE / "work" / "native_archives" / "atomic_six_pending.bin"
OUTPUT = HERE / "work" / "six_pending_slot_cross"
SLOT_ORDER = [6, 1, 2, 3, 4, 5]
LOAD_OFFSETS = [0x04, 0x12, 0x20, 0x2E, 0x3C, 0x4A]
ATOMIC_OFFSETS = [0x80, 0xC2, 0xE2, 0x102, 0x122, 0x142]
LOAD_TOKENS = {1: 0x1100, 2: 0x5100, 3: 0x9100,
               4: 0xD100, 5: 0x1101, 6: 0x5101}
PREPS = [(0x76, 10), (0xBE, 4), (0xD8, 10),
         (0xF8, 10), (0x118, 10), (0x138, 10)]


def set_bits(data: bytearray, start: int, count: int, value: int) -> None:
    for bit in range(count):
        absolute = start + bit
        mask = 1 << (absolute & 7)
        if value & (1 << bit):
            data[absolute >> 3] |= mask
        else:
            data[absolute >> 3] &= ~mask


def dead_iadd10(register: int) -> bytes:
    data = bytearray.fromhex("9f015400020000a81705")
    set_bits(data, 25, 7, register)
    set_bits(data, 42, 7, register)
    set_bits(data, 51, 7, register)
    return bytes(data)


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
    for offset, slot in zip(LOAD_OFFSETS, SLOT_ORDER):
        token = LOAD_TOKENS[slot]
        if main[offset + 8:offset + 10] != token.to_bytes(2, "big"):
            raise ValueError(f"unexpected load token at main+{offset:#x}")
    for offset, slot in zip(ATOMIC_OFFSETS, SLOT_ORDER):
        raw = main[offset:offset + 14]
        mask = ((raw[1] >> 4) & 0x0F) | ((raw[2] & 3) << 4)
        if mask != 1 << (slot - 1):
            raise ValueError(f"unexpected atomic dependency at main+{offset:#x}")

    replacement4 = bytes((0xCC, 0xA0, 0x10, 0x66))
    replacement10 = dead_iadd10(60)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for input_slot in range(1, 7):
        for result_slot in range(1, 7):
            # Start from Metal's six-element schedule and swap the desired
            # input slot onto the atomic with the requested native return
            # slot.  The occupied set remains exactly {1..6} throughout.
            permutation = SLOT_ORDER.copy()
            result_index = SLOT_ORDER.index(result_slot)
            input_index = permutation.index(input_slot)
            permutation[result_index], permutation[input_index] = (
                permutation[input_index], permutation[result_index]
            )
            archive = bytearray(blob)
            for offset, length in PREPS:
                replacement = replacement4 if length == 4 else replacement10
                archive[main_offset + offset:main_offset + offset + length] = replacement
            for offset, slot in zip(LOAD_OFFSETS, permutation):
                token = LOAD_TOKENS[slot]
                archive[main_offset + offset + 8] = token >> 8
                archive[main_offset + offset + 9] = token & 0xFF
            for offset, slot in zip(ATOMIC_OFFSETS, permutation):
                b1, b2 = dependency_bytes(main[offset + 1], main[offset + 2],
                                          slot)
                archive[main_offset + offset + 1] = b1
                archive[main_offset + offset + 2] = b2
            name = f"s{input_slot}_r{result_slot}.bin"
            (OUTPUT / name).write_bytes(archive)
            rows.append({"archive": name, "prep": "none",
                         "input_slot": input_slot,
                         "result_slot": result_slot,
                         "slot_permutation": permutation})

    (OUTPUT / "manifest.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(rows)} variants to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
