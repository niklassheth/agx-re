#!/usr/bin/env python3
"""Summarize the two-field IMAD cross and verify its changed dataflow."""

from __future__ import annotations

import hashlib
import json
import pathlib
import struct


HERE = pathlib.Path(__file__).resolve().parent
R30 = HERE.parent / "EXP-M4-30-apple9-route-semantics"
CAPTURES = HERE / "captures/imad-cross"
EXPECTED = R30 / (
    "generated/oracles/"
    "r30_iselect_atomic_u32_direct_route12_split_store_live0.bin"
)
WORDS = 1024
DISPATCH = 256
MASK32 = 0xFFFFFFFF


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def input_word(lane: int) -> int:
    return (0x10203040 ^ lane * 0x01010101) & MASK32


def expected_srcb8(control: bytes) -> bytes:
    words = list(struct.unpack(f"<{WORDS}I", control))
    for lane in range(DISPATCH):
        p1 = input_word((lane + 37) & (WORDS - 1))
        words[lane + DISPATCH] = (p1 * 0x045D9F3B) & MASK32
    return struct.pack(f"<{WORDS}I", *words)


def main() -> int:
    expected = EXPECTED.read_bytes()
    srcb8_oracle = expected_srcb8(expected)
    variants = ("control", "b1hi_8_to_16", "srcB_4_to_8", "both")
    results = {}
    for variant in variants:
        repetitions = []
        outputs = []
        for repeat in (1, 2):
            root = CAPTURES / f"{variant}-rep{repeat}"
            output = (root / "output.bin").read_bytes()
            outputs.append(output)
            status = next(
                line.split(None, 1)[1]
                for line in (root / "stdout.log").read_text().splitlines()
                if line.startswith("STATUS ")
            )
            changed = [index for index, (left, right) in
                       enumerate(zip(expected, output)) if left != right]
            repetitions.append({
                "repeat": repeat,
                "status": status,
                "output_sha256": sha(output),
                "exact_native_oracle": output == expected,
                "exact_srcB8_oracle": output == srcb8_oracle,
                "changed_byte_count": len(changed),
                "first_changed_byte": changed[0] if changed else None,
                "last_changed_byte": changed[-1] if changed else None,
                "iselect_region_exact": output[:DISPATCH * 4] ==
                    expected[:DISPATCH * 4],
            })
        results[variant] = {
            "repetitions_identical": outputs[0] == outputs[1],
            "repetitions": repetitions,
        }
    output = {
        "schema_version": 1,
        "source_case": (
            "r30_iselect_atomic_u32_direct_route12_split_store_live0_a"
        ),
        "interpretation": {
            "b1hi_8_to_16": (
                "inert in this carrier: full output remains exact"
            ),
            "srcB_4_to_8": (
                "changes only the separately stored prior-IMAD value from "
                "p0 to p1; the following ISELECT region remains exact"
            ),
        },
        "results": results,
    }
    (HERE / "IMAD_CROSS_RESULTS.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        variant: {
            "exact_native": item["repetitions"][0]["exact_native_oracle"],
            "exact_srcB8": item["repetitions"][0]["exact_srcB8_oracle"],
            "iselect_exact": item["repetitions"][0]["iselect_region_exact"],
        }
        for variant, item in results.items()
    }, sort_keys=True))
    return int(
        not results["control"]["repetitions"][0]["exact_native_oracle"] or
        not results["b1hi_8_to_16"]["repetitions"][0]["exact_native_oracle"] or
        not results["srcB_4_to_8"]["repetitions"][0]["exact_srcB8_oracle"] or
        not results["both"]["repetitions"][0]["exact_srcB8_oracle"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
