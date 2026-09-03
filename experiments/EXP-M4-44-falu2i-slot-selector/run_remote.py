#!/usr/bin/env python3
"""Execute the FALU2I producer-slot x consumer-selector cross on T8132."""

from __future__ import annotations

import argparse
import json
import pathlib
import struct
import subprocess
import time


ROOT = pathlib.Path(__file__).resolve().parent
AGXTEST = ROOT / "tools" / "agxtest.py"
SOURCE = ROOT / "kernel.metal"
WORK = ROOT / "work"
ARCHIVE = WORK / "falu2i_slot_cross.archive.bin"

# Two-byte device-load producer tags established independently by EXP-M4-42.
TOKENS = {
    1: "1100",
    2: "5100",
    3: "9100",
    4: "d100",
    5: "1101",
    6: "5101",
}

INPUT_FLOATS = (1.0, -2.0, 3.25, 100.0)
OUTPUT_FLOATS = (2.5, -0.5, 4.75, 101.5)


def i32_bits(value: float) -> int:
    unsigned = struct.unpack("<I", struct.pack("<f", value))[0]
    return unsigned if unsigned < (1 << 31) else unsigned - (1 << 32)


INPUT_BITS = tuple(i32_bits(value) for value in INPUT_FLOATS)
ORACLE_BITS = [i32_bits(value) for value in OUTPUT_FLOATS]


def csv(values) -> str:
    return ",".join(str(value) for value in values)


def base_command(*, dump_main: bool = False) -> list[str]:
    command = [
        "python3", str(AGXTEST),
        "--source", str(SOURCE),
        "--function", "falu2i_slot_cross",
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(ARCHIVE), "--workdir", str(WORK),
        "--buf", f"0={csv((0, 0, 0, 0))}",
        "--buf", f"1={csv(INPUT_BITS)}",
        "--out", "0=4", "--run-timeout", "15",
    ]
    if dump_main:
        command.append("--dump-main")
    return command


def invoke(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, text=True, capture_output=True, timeout=25, check=False)


def parse_output(process: subprocess.CompletedProcess[str]) -> tuple[str, list[int] | None]:
    status = "UNKNOWN"
    values = None
    for line in process.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(maxsplit=1)[1]
        elif line.startswith("RESULT 0 "):
            values = [int(value) for value in line.split()[2:]]
    return status, values


def extract_main() -> bytes:
    process = invoke(base_command(dump_main=True))
    if process.returncode != 0:
        raise RuntimeError(
            f"native control failed ({process.returncode})\n"
            f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}")
    status, values = parse_output(process)
    if status != "OK" or values != ORACLE_BITS:
        raise RuntimeError(
            f"native control mismatch: status={status} values={values} "
            f"oracle={ORACLE_BITS}\n{process.stdout}\n{process.stderr}")
    for line in process.stdout.splitlines():
        if line.startswith("MAIN_ORIG "):
            return bytes.fromhex(line.split(maxsplit=1)[1])
    raise RuntimeError("agxtest did not report MAIN_ORIG")


def locate_instructions(main: bytes) -> tuple[int, int]:
    """Use the experiment's pinned decoder only to locate our own instructions."""
    import sys

    sys.path.insert(0, str(ROOT / "agx-isa"))
    import isadb  # pylint: disable=import-error,import-outside-toplevel

    records, leftover = isadb.disassemble(main)
    if leftover:
        raise RuntimeError(f"decoder left {len(leftover)} trailing bytes")
    offset = 0
    located = []
    for record in records:
        located.append((offset, record))
        offset += record["length"]
    loads = [(offset, record) for offset, record in located
             if record["mnemonic"] == "device_load"]
    consumers = [(offset, record) for offset, record in located
                 if record["mnemonic"] == "falu2i"]
    if len(loads) != 1 or len(consumers) != 1:
        raise RuntimeError(
            f"expected one device_load and one falu2i, got "
            f"{len(loads)} and {len(consumers)}")
    load_offset, load = loads[0]
    consumer_offset, consumer = consumers[0]
    if consumer_offset != load_offset + load["length"]:
        raise RuntimeError(
            f"producer is not adjacent: load={load_offset:#x}, "
            f"consumer={consumer_offset:#x}")
    if consumer["length"] != 6:
        raise RuntimeError("consumer is not the six-byte FALU2I form")
    return load_offset, consumer_offset


def consumer_splice(main: bytes, offset: int, selector: int) -> str:
    old = main[offset + 5]
    new = (old & 0x1F) | ((selector & 7) << 5)
    return f"_agc.main@{offset + 5:#x}={new:02x}"


def execute(main: bytes, load_offset: int, consumer_offset: int,
            producer_slot: int, selector: int) -> dict:
    command = base_command()
    command += [
        "--splice", f"_agc.main@{load_offset + 8:#x}={TOKENS[producer_slot]}",
        "--splice", consumer_splice(main, consumer_offset, selector),
    ]
    started = time.monotonic()
    process = invoke(command)
    status, values = parse_output(process)
    return {
        "producer_slot": producer_slot,
        "consumer_selector": selector,
        "relation": "matching" if producer_slot == selector else "mismatched",
        "status": status,
        "values": values,
        "oracle": ORACLE_BITS,
        "exact": status == "OK" and values == ORACLE_BITS,
        "returncode": process.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    WORK.mkdir(exist_ok=True)
    native = extract_main()
    load_offset, consumer_offset = locate_instructions(native)

    passes = []
    orders = (
        ("forward", [(slot, selector) for slot in range(1, 7)
                     for selector in range(0, 8)]),
        ("reverse", [(slot, selector) for slot in range(6, 0, -1)
                     for selector in range(7, -1, -1)]),
    )
    for pass_name, cases in orders:
        records = []
        for producer_slot, selector in cases:
            record = execute(native, load_offset, consumer_offset,
                             producer_slot, selector)
            records.append(record)
            print(
                f"{pass_name:7} producer={producer_slot} selector={selector} "
                f"exact={int(record['exact'])} status={record['status']} "
                f"values={record['values']}", flush=True)
        passes.append({"name": pass_name, "records": records})

    payload = {
        "schema_version": 1,
        "run_id": args.run_id,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "native_main_hex": native.hex(),
        "load_offset": load_offset,
        "producer_token_offset": load_offset + 8,
        "consumer_offset": consumer_offset,
        "consumer_selector_bits": [45, 47],
        "input_bits": list(INPUT_BITS),
        "oracle_bits": ORACLE_BITS,
        "passes": passes,
    }
    result_path = ROOT / f"RAW_{args.run_id}.json"
    result_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    records = [record for run_pass in passes for record in run_pass["records"]]
    in_scope = [record for record in records
                if record["consumer_selector"] <= 6]
    matching = [record for record in in_scope
                if record["relation"] == "matching"]
    mismatched = [record for record in in_scope
                  if record["relation"] == "mismatched"]
    selector7 = [record for record in records
                 if record["consumer_selector"] == 7]
    passed = all(record["exact"] for record in matching) and \
        not any(record["exact"] for record in mismatched) and \
        all(record["status"] == "OK" for record in records)
    print(
        f"SUMMARY records={len(records)} matching_exact="
        f"{sum(record['exact'] for record in matching)}/{len(matching)} "
        f"mismatched_exact={sum(record['exact'] for record in mismatched)}/"
        f"{len(mismatched)} selector7_exact="
        f"{sum(record['exact'] for record in selector7)}/{len(selector7)} "
        f"pass={int(passed)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
