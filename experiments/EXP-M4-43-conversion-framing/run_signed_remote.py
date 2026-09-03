#!/usr/bin/env python3
"""Map the low two bits of F2I byte +8 on the own-source carrier."""

from __future__ import annotations

import json
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parent
LOW_BITS_INPUT = [
    -1_080_033_280, -1_071_644_672, 1_081_081_856, -947_912_768,
]
TIE_INPUT = [1_075_838_976, 1_080_033_280, -1_071_644_672, -1_067_450_368]
TYPE_INPUT = [1_325_400_065, 1_333_788_671, -1_082_130_432, 1_199_570_880]


def parse(stdout: str) -> tuple[str, list[int] | None]:
    status = "UNKNOWN"
    values = None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(maxsplit=1)[1]
        elif line.startswith("RESULT 0 "):
            values = [int(value) for value in line.split()[2:]]
    return status, values


def run(panel: str, b7: int, b8: int, inputs: list[int]) -> dict:
    command = [
            "python3", str(ROOT / "tools" / "agxtest.py"),
            "--source", str(ROOT / "consumers.metal"),
            "--function", "f2u_load", "--grid", "4", "--tg", "4",
            "--int", "--archive", str(ROOT / "f2u_load.archive.bin"),
            "--workdir", str(ROOT / "mutation-work"),
            "--buf", "0=0,0,0,0",
            "--buf", "1=" + ",".join(str(value) for value in inputs),
            "--out", "0=4", "--run-timeout", "15",
            # Use the established signed-I32 conversion selector, then vary
            # only the low two bits of the disputed continuation byte.
            "--splice", f"_agc.main@0x19={b7:02x}",
            "--splice", f"_agc.main@0x1a={b8:02x}00",
        ]
    process = subprocess.run(
        command, text=True, capture_output=True, timeout=25, check=False)
    status, values = parse(process.stdout)
    record = {
        "panel": panel,
        "byte7": b7,
        "byte8": b8,
        "input_f32_bits_as_i32": inputs,
        "status": status,
        "values": values,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }
    print(f"{panel} byte7={b7:02x} byte8={b8:02x} {status} {values}",
          flush=True)
    return record


def main() -> int:
    records = []
    for descriptor in range(4):
        records.append(run("low_bits", 0x48, descriptor, LOW_BITS_INPUT))

    for descriptor in (1, 3):
        records.append(run("rounding_ties", 0x48, descriptor, TIE_INPUT))

    for byte7 in (0x08, 0x48):
        for descriptor in (2, 3):
            records.append(run("type_cross", byte7, descriptor, TYPE_INPUT))

    (ROOT / "SIGNED_RESULTS.json").write_text(json.dumps({
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "panels": {
            "low_bits": {
                "input_values": [-1.25, -2.5, 3.75, -65535.75],
            },
            "rounding_ties": {
                "input_values": [2.5, 3.5, -2.5, -3.5],
            },
            "type_cross": {
                "input_values": [2147483904.0, 4294967040.0, -1.0, 65535.75],
            },
        },
        "records": records,
    }, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
