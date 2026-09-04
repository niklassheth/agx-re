#!/usr/bin/env python3
"""Build same-size native-archive mutations for DEVICE_ATOMIC_PREP research."""

from __future__ import annotations

import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "shdump"))

import agxparse  # noqa: E402


COMPACT_ARCHIVE = (
    ROOT / "experiments" / "EXP-M4-47-atomic-semantics" /
    "archives" / "dev_contended_add.bin"
)
LONG_ARCHIVE = (
    ROOT / "experiments" / "EXP-M4-47-atomic-semantics" /
    "archives" / "dev_add.bin"
)
OUTPUT = HERE / "work" / "mutations"


def patch_archive(source: Path, edits: dict[int, int], expected: dict[int, int],
                  destination: Path) -> dict:
    blob = bytearray(source.read_bytes())
    main_offset, main_size = agxparse.locate_region(
        bytes(blob), "_agc.main", stage="compute"
    )
    before = bytes(blob[main_offset:main_offset + main_size])
    for offset, value in expected.items():
        actual = before[offset]
        if actual != value:
            raise ValueError(
                f"{source.name}: main+{offset:#x} is {actual:#x}, expected {value:#x}"
            )
    for offset, value in edits.items():
        blob[main_offset + offset] = value
    destination.write_bytes(blob)
    after = bytes(blob[main_offset:main_offset + main_size])
    return {
        "archive": destination.name,
        "source_archive": str(source),
        "main_offset": main_offset,
        "main_size": main_size,
        "edits": {f"{offset:#x}": value for offset, value in edits.items()},
        "before": before.hex(),
        "after": after.hex(),
    }


def atomic_mask_edits(atomic_offset: int, mask: int,
                      original_b1: int, original_b2: int) -> dict[int, int]:
    return {
        atomic_offset + 1: (original_b1 & 0x0f) | ((mask & 0x0f) << 4),
        atomic_offset + 2: (original_b2 & 0xfc) | ((mask >> 4) & 0x03),
    }


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []

    compact_prep = 0x1A
    compact_atomic = 0x1E
    compact_expected = {
        compact_prep + 0: 0x0B,
        compact_prep + 1: 0x00,
        compact_prep + 2: 0x00,
        compact_prep + 3: 0x02,
        compact_atomic + 0: 0x67,
        compact_atomic + 1: 0x11,
        compact_atomic + 2: 0x54,
    }
    variants: dict[str, dict[int, int]] = {"baseline": {}}
    for value in (0x00, 0x01, 0x03, 0x04, 0x05, 0x06, 0x08,
                  0x10, 0x20, 0x40, 0x80, 0xFF):
        variants[f"opdesc_{value:02x}"] = {compact_prep + 3: value}
    for register in (1, 2, 3, 7, 15):
        variants[f"dst_r{register}"] = {compact_prep: (register << 4) | 0x0B}
        variants[f"src_r{register}"] = {compact_prep + 1: register}
    for value in (0x01, 0x20, 0x21, 0x40, 0x60, 0x80):
        variants[f"class_{value:02x}"] = {compact_prep + 2: value}
    for mask in (0, 2, 4, 8, 16, 32, 63):
        variants[f"atomic_dep_{mask:02x}"] = atomic_mask_edits(
            compact_atomic, mask, 0x11, 0x54
        )
    variants["opdesc_00_dep_00"] = {
        compact_prep + 3: 0x00,
        **atomic_mask_edits(compact_atomic, 0, 0x11, 0x54),
    }
    variants["opdesc_02_dep_00"] = {
        **atomic_mask_edits(compact_atomic, 0, 0x11, 0x54),
    }
    variants["opdesc_00_dep_01"] = {compact_prep + 3: 0x00}

    for name, edits in variants.items():
        destination = OUTPUT / f"compact_{name}.bin"
        row = patch_archive(
            COMPACT_ARCHIVE, edits, compact_expected, destination
        )
        row.update({"family": "compact", "case": name,
                    "function": "dev_contended_add"})
        manifest.append(row)

    # The long record is always emitted for a returned atomic whose operand is
    # a directly pending scalar device load in the native corpus.  Keep its
    # length-selecting byte intact and first sweep fields that can be varied
    # without changing instruction boundaries.
    long_prep = 0x12
    long_expected = {
        long_prep + 0: 0x0B,
        long_prep + 1: 0x00,
        long_prep + 2: 0x06,
        long_prep + 3: 0x00,
        long_prep + 4: 0x20,
        long_prep + 5: 0x00,
        long_prep + 6: 0x00,
        long_prep + 7: 0x14,
        long_prep + 8: 0x00,
        long_prep + 9: 0x00,
        0x1C: 0x67,
        0x1D: 0x01,
        0x1E: 0x56,
    }
    long_variants: dict[str, dict[int, int]] = {"baseline": {}}
    # Preserve the native code extent while removing the ten-byte prep.  Zero
    # words are not standalone NOPs (the hardware faults on a run of them), so
    # use five ordinary two-byte MOV_IMM writes to otherwise dead r10..r14.
    # The compact variant uses three such writes for its remaining six bytes.
    dead_moves = bytes((0xac, 1, 0xbc, 2, 0xcc, 3, 0xdc, 4, 0xec, 5))
    long_variants["no_prep_dead_moves"] = {
        long_prep + index: value for index, value in enumerate(dead_moves)
    }
    compact_with_moves = bytes((0x0b, 0x00, 0x00, 0x02,
                                0xcc, 3, 0xdc, 4, 0xec, 5))
    long_variants["compact_prep_dead_moves"] = {
        long_prep + index: value
        for index, value in enumerate(compact_with_moves)
    }
    # Retain the all-zero negative controls: they establish that 0x0000 is
    # context/padding rather than a freely insertable standalone NOP.
    long_variants["no_prep_pad10"] = {
        long_prep + index: 0x00 for index in range(10)
    }
    long_variants["compact_prep_pad6"] = {
        long_prep + 0: 0x0b,
        long_prep + 1: 0x00,
        long_prep + 2: 0x00,
        long_prep + 3: 0x02,
        **{long_prep + index: 0x00 for index in range(4, 10)},
    }
    for value in (0x00, 0x20, 0x40, 0x60, 0x80, 0xA0, 0xC0, 0xE0):
        if value != 0x20:
            long_variants[f"byte4_{value:02x}"] = {long_prep + 4: value}
    for value in (0x00, 0x04, 0x10, 0x14, 0x20, 0x40, 0x80, 0xFF):
        if value != 0x14:
            long_variants[f"byte7_{value:02x}"] = {long_prep + 7: value}
    for index in (3, 5, 6, 8, 9):
        long_variants[f"byte{index}_01"] = {long_prep + index: 0x01}
    for mask in (33, 34, 36, 40, 48, 63):
        # These preserve the required slot-6 bit while adding another wait.
        long_variants[f"atomic_dep_{mask:02x}"] = atomic_mask_edits(
            0x1C, mask, 0x01, 0x56
        )

    for name, edits in long_variants.items():
        destination = OUTPUT / f"long_{name}.bin"
        row = patch_archive(LONG_ARCHIVE, edits, long_expected, destination)
        row.update({"family": "long", "case": name, "function": "dev_add"})
        manifest.append(row)

    sweep_output = HERE / "work" / "opdesc_sweep"
    sweep_output.mkdir(parents=True, exist_ok=True)
    for value in range(256):
        patch_archive(
            COMPACT_ARCHIVE,
            {compact_prep + 3: value},
            compact_expected,
            sweep_output / f"compact_desc_{value:02x}.bin",
        )
    patch_archive(COMPACT_ARCHIVE, {}, compact_expected,
                  sweep_output / "compact_baseline.bin")

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )
    print(f"wrote {len(manifest)} targeted variants to {OUTPUT}")
    print(f"wrote 256 op-desc variants to {sweep_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
