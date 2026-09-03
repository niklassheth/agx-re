#!/usr/bin/env python3
"""Run native controls and bits-12:17 mutations on the macOS target.

This script is staged next to ``consumers.metal`` and ``tools/agxtest.py``.
All buffers are passed as signed int32 words so floating-point tests can compare
their complete bit patterns rather than tolerate numeric differences.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import time


ROOT = pathlib.Path(__file__).resolve().parent
AGXTEST = ROOT / "tools" / "agxtest.py"
SOURCE = ROOT / "consumers.metal"
WORK = ROOT / "mutation-work"


CASES = {
    "u2f_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [0, 1, 7, 16_777_215]},
        "oracle": [0, 1_065_353_216, 1_088_421_888, 1_266_679_807],
    },
    "i2f_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [-7, 0, 1, 1_234_567]},
        "oracle": [-1_059_061_760, 0, 1_065_353_216, 1_234_613_304],
    },
    "f2u_load": {
        "consumer": 0x12,
        "buffers": {
            0: [0] * 4,
            1: [0, 1_065_353_216, 1_089_994_752, 1_199_570_688],
        },
        "oracle": [0, 1, 7, 65_535],
    },
    "reciprocal_load": {
        "consumer": 0x12,
        "buffers": {
            0: [0] * 4,
            1: [1_065_353_216, 1_073_741_824, 1_082_130_432, 1_090_519_040],
        },
        "oracle": [1_065_353_216, 1_056_964_608, 1_048_576_000, 1_040_187_392],
    },
    "popcount_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [0, 1, 61_680, -1]},
        "oracle": [0, 1, 8, 32],
    },
    "clz_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [1, 16, 1_048_576, -2_147_483_648]},
        "oracle": [31, 27, 11, 0],
    },
    "shift_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [0, 32, 305_419_896, -1]},
        "oracle": [0, 1, 9_544_371, 134_217_727],
    },
    "imad_load": {
        "consumer": 0x2E,
        "buffers": {
            0: [0] * 4,
            1: [0, 1, 7, 101],
            2: [5, 11, 13, 103],
            3: [17, 19, 23, 107],
        },
        "oracle": [17, 30, 114, 10_510],
    },
    "extract_load": {
        "consumer": 0x12,
        "buffers": {0: [0] * 4, 1: [0, 32, -559_038_737, -1]},
        "oracle": [0, 1, 1_527, 2_047],
    },
    "insert_load": {
        "consumer": 0x20,
        "buffers": {
            0: [0] * 4,
            1: [-559_038_737, 0, -1, 305_419_896],
            2: [305_419_896, -1, 0, 0x155],
        },
        "oracle": [-559_072_145, 65_408, -65_409, 305_441_528],
    },
    "iadd_load": {
        "consumer": 0x20,
        "buffers": {
            0: [0] * 4,
            1: [0, 1, 7, 101],
            2: [5, 11, 13, 103],
        },
        "oracle": [5, 12, 20, 204],
    },
    "isub_load": {
        "consumer": 0x20,
        "buffers": {
            0: [0] * 4,
            1: [0, 1, 7, 101],
            2: [5, 11, 13, 103],
        },
        "oracle": [-5, -10, -6, -2],
    },
}

# Native low-pressure programs use slot 6 (mask bit 5).  Include every one-hot
# value, zero, all bits, and two multi-bit combinations.
MASKS = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x21, 0x30, 0x3F)


def signed_csv(values: list[int]) -> str:
    return ",".join(str(value) for value in values)


def encode_field(mask: int, native_b1: int, native_b2: int) -> bytes:
    """Replace instruction bits 12--17 while preserving their neighbors."""
    b1 = (native_b1 & 0x0F) | ((mask & 0x0F) << 4)
    b2 = (native_b2 & 0xFC) | ((mask >> 4) & 0x03)
    return bytes((b1, b2))


def parse(stdout: str) -> tuple[str, list[int] | None]:
    status = "UNKNOWN"
    values = None
    for line in stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(maxsplit=1)[1]
        elif line.startswith("RESULT 0 "):
            values = [int(value) for value in line.split()[2:]]
    return status, values


def main() -> int:
    WORK.mkdir(exist_ok=True)
    records = []
    for function, spec in CASES.items():
        archive = ROOT / "consumers" / f"{function}.archive.bin"
        main_dump = subprocess.run(
            ["python3", str(AGXTEST), "--source", str(SOURCE),
             "--function", function, "--grid", "4", "--tg", "4", "--int",
             "--archive", str(archive), "--workdir", str(WORK), "--dump-main",
             *sum((["--buf", f"{index}={signed_csv(values)}"]
                   for index, values in spec["buffers"].items()), []),
             "--out", "0=4", "--run-timeout", "15"],
            text=True, capture_output=True, timeout=25, check=False)
        main_hex = next(line.split(maxsplit=1)[1]
                        for line in main_dump.stdout.splitlines()
                        if line.startswith("MAIN_ORIG "))
        main_bytes = bytes.fromhex(main_hex)
        consumer = spec["consumer"]
        native_b1, native_b2 = main_bytes[consumer + 1:consumer + 3]

        for mask in MASKS:
            field = encode_field(mask, native_b1, native_b2)
            command = [
                "python3", str(AGXTEST),
                "--source", str(SOURCE), "--function", function,
                "--grid", "4", "--tg", "4", "--int",
                "--archive", str(archive), "--workdir", str(WORK),
                "--out", "0=4", "--run-timeout", "15",
                "--splice", f"_agc.main@{consumer + 1:#x}={field.hex()}",
            ]
            for index, values in spec["buffers"].items():
                command += ["--buf", f"{index}={signed_csv(values)}"]
            started = time.monotonic()
            process = subprocess.run(
                command, text=True, capture_output=True, timeout=25,
                check=False)
            status, values = parse(process.stdout)
            exact = status == "OK" and values == spec["oracle"]
            record = {
                "function": function,
                "mask": mask,
                "field_hex": field.hex(),
                "native_field_hex": bytes((native_b1, native_b2)).hex(),
                "status": status,
                "values": values,
                "oracle": spec["oracle"],
                "exact": exact,
                "returncode": process.returncode,
                "elapsed_seconds": time.monotonic() - started,
                "stdout": process.stdout,
                "stderr": process.stderr,
            }
            records.append(record)
            print(f"{function:16} mask={mask:02x} field={field.hex()} "
                  f"status={status:12} exact={int(exact)} values={values}",
                  flush=True)

    output = {
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "records": records,
    }
    (ROOT / "HARDWARE_RESULTS.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    failures = sum(not record["exact"] for record in records)
    print(f"SUMMARY records={len(records)} nonexact={failures}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
