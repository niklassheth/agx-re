#!/usr/bin/env python3
"""Execute the F2U suffix/framing discriminator on a macOS M4 target."""

from __future__ import annotations

import json
import pathlib
import subprocess
import time


ROOT = pathlib.Path(__file__).resolve().parent
AGXTEST = ROOT / "tools" / "agxtest.py"
SOURCE = ROOT / "consumers.metal"
ARCHIVE = ROOT / "f2u_load.archive.bin"
WORK = ROOT / "mutation-work"

# The own-source program is:
#   get_sr (4), device_load (14), f2u (disputed 8/10), device_store (14), stop (4)
# The apparent conversion begins at 0x12 and its disputed suffix at 0x1a.
SUFFIX_OFFSET = 0x1A

INPUT = [1_065_353_216, 1_073_741_824, 1_081_081_856, 1_199_570_688]
NATIVE_ORACLE = [1, 2, 3, 65_535]

VARIANTS = (
    ("native", "0200", NATIVE_ORACLE),
    ("tail_03", "0300", NATIVE_ORACLE),
    # Each is a valid, independently established two-byte mov_imm if decoding
    # starts at the disputed boundary.  All target r0, which the following
    # store reads.  Three constants make accidental agreement implausible.
    ("mov_r0_7", "0c07", [7, 7, 7, 7]),
    ("mov_r0_42", "0c2a", [42, 42, 42, 42]),
    ("mov_r0_99", "0c63", [99, 99, 99, 99]),
    # If separately decoded this writes unused r15 and must preserve F2U.
    ("mov_r15_0", "fc00", NATIVE_ORACLE),
)


def parse(stdout: str) -> tuple[str, list[int] | None, str | None]:
    status = "UNKNOWN"
    values = None
    main_hex = None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(maxsplit=1)[1]
        elif line.startswith("RESULT 0 "):
            values = [int(value) for value in line.split()[2:]]
        elif line.startswith("MAIN_ORIG "):
            main_hex = line.split(maxsplit=1)[1]
    return status, values, main_hex


def run(label: str, suffix: str) -> dict:
    command = [
        "python3", str(AGXTEST),
        "--source", str(SOURCE), "--function", "f2u_load",
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(ARCHIVE), "--workdir", str(WORK),
        "--buf", "0=0,0,0,0",
        "--buf", "1=" + ",".join(str(value) for value in INPUT),
        "--out", "0=4", "--run-timeout", "15", "--dump-main",
        "--splice", f"_agc.main@{SUFFIX_OFFSET:#x}={suffix}",
    ]
    started = time.monotonic()
    process = subprocess.run(
        command, text=True, capture_output=True, timeout=25, check=False)
    status, values, main_hex = parse(process.stdout)
    return {
        "label": label,
        "suffix": suffix,
        "status": status,
        "values": values,
        "main_hex": main_hex,
        "returncode": process.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    WORK.mkdir(exist_ok=True)
    records = []
    # Recheck the native control between every mutation so a prior fault or
    # stale target state cannot masquerade as a framing result.
    for label, suffix, independent_oracle in VARIANTS:
        if label != "native":
            control = run(f"control_before_{label}", "0200")
            control["native_exact"] = (
                control["status"] == "OK" and
                control["values"] == NATIVE_ORACLE)
            records.append(control)
            print(control["label"], control["status"], control["values"],
                  flush=True)

        record = run(label, suffix)
        record["native_exact"] = (
            record["status"] == "OK" and record["values"] == NATIVE_ORACLE)
        record["independent_move_exact"] = (
            record["status"] == "OK" and
            record["values"] == independent_oracle)
        records.append(record)
        print(label, suffix, record["status"], record["values"], flush=True)

    result = {
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "native_oracle": NATIVE_ORACLE,
        "records": records,
    }
    (ROOT / "HARDWARE_RESULTS.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
