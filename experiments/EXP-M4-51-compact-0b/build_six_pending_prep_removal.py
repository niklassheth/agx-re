#!/usr/bin/env python3
"""Remove each native prep from a six-load/six-returned-atomic carrier."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "shdump"))

import agxparse  # noqa: E402


SOURCE = HERE / "work" / "native_archives" / "atomic_six_pending.bin"
OUTPUT = HERE / "work" / "six_pending_prep_removal"


def set_bits(data: bytearray, start: int, count: int, value: int) -> None:
    for bit in range(count):
        absolute = start + bit
        mask = 1 << (absolute & 7)
        if value & (1 << bit):
            data[absolute >> 3] |= mask
        else:
            data[absolute >> 3] &= ~mask


def dead_iadd10(register: int) -> bytes:
    """Encode rN = rN + rN with no pending dependency in an unused GPR."""
    data = bytearray.fromhex("9f015400020000a81705")
    set_bits(data, 25, 7, register)
    set_bits(data, 42, 7, register)
    set_bits(data, 51, 7, register)
    return bytes(data)


def main() -> int:
    blob = bytearray(SOURCE.read_bytes())
    main_offset, main_size = agxparse.locate_region(
        bytes(blob), "_agc.main", stage="compute"
    )
    main = bytes(blob[main_offset:main_offset + main_size])
    preps = {
        "s6": (0x76, bytes.fromhex("0b000600200000140000")),
        "s1": (0xBE, bytes.fromhex("0b0000c2")),
        "s2": (0xD8, bytes.fromhex("0b000600200000840000")),
        "s3": (0xF8, bytes.fromhex("0b000600200000880000")),
        "s4": (0x118, bytes.fromhex("0b0006002000008c0000")),
        "s5": (0x138, bytes.fromhex("0b000600200000900000")),
    }
    for name, (offset, expected) in preps.items():
        actual = main[offset:offset + len(expected)]
        if actual != expected:
            raise ValueError(f"{name} main+{offset:#x}: {actual.hex()} != "
                             f"{expected.hex()}")

    # Write only high scratch registers beyond this carrier's live range.
    # The first attempted control used compact MOV_IMM r15 and demonstrated
    # that it really does overwrite this carrier's pending r15 load; it was
    # therefore rejected rather than interpreting the resulting corruption as
    # prep semantics.  These replacements are ordinary, independently known
    # instructions of exactly the required lengths.
    replacement4 = bytes((0xCC, 0xA0, 0x10, 0x66))  # get_sr r60, global_id.x
    replacement10 = dead_iadd10(60)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cases = {"baseline": []}
    for name in preps:
        cases[f"remove_{name}"] = [name]
    cases["remove_all"] = list(preps)

    rows = []
    for case, removed in cases.items():
        archive = bytearray(blob)
        for name in removed:
            offset, expected = preps[name]
            replacement = replacement4 if len(expected) == 4 else replacement10
            archive[main_offset + offset:main_offset + offset + len(expected)] = replacement
        filename = f"{case}.bin"
        (OUTPUT / filename).write_bytes(archive)
        rows.append({"archive": filename, "removed": removed})

    (OUTPUT / "manifest.json").write_text(
        json.dumps(rows, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(rows)} variants to {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
