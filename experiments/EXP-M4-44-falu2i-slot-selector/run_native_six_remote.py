#!/usr/bin/env python3
"""Sweep six naturally allocated load->FALU2I selector relationships."""

from __future__ import annotations

import json
import pathlib
import struct

import run_remote as one


ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "kernel_multi.metal"
WORK = ROOT / "work-six"
ARCHIVE = WORK / "falu2i_six_loads.archive.bin"

INPUTS = (
    (1.0, 2.0, 3.0, 4.0),
    (10.0, 20.0, 30.0, 40.0),
    (100.0, 200.0, 300.0, 400.0),
    (1000.0, 2000.0, 3000.0, 4000.0),
    (5.0, 6.0, 7.0, 8.0),
    (50.0, 60.0, 70.0, 80.0),
)
ADDS = (1.5, 2.5, 3.5, 4.5, 5.5, 6.5)
EXPECTED_NATIVE_SELECTORS = (6, 1, 2, 3, 4, 5)


def i32_bits(value: float) -> int:
    unsigned = struct.unpack("<I", struct.pack("<f", value))[0]
    return unsigned if unsigned < (1 << 31) else unsigned - (1 << 32)


def csv(values) -> str:
    return ",".join(str(value) for value in values)


ORACLE_FLOATS = tuple(
    value
    for lane in range(4)
    for value in tuple(INPUTS[source][lane] + ADDS[source]
                       for source in range(6)) + (0.0, 0.0)
)
ORACLE_BITS = [i32_bits(value) for value in ORACLE_FLOATS]


def command(*, dump_main: bool = False) -> list[str]:
    result = [
        "python3", str(one.AGXTEST),
        "--source", str(SOURCE), "--function", "falu2i_six_loads",
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(ARCHIVE), "--workdir", str(WORK),
        "--buf", f"0={csv([0] * 32)}", "--out", "0=32",
        "--run-timeout", "15",
    ]
    for index, values in enumerate(INPUTS, start=1):
        result += ["--buf", f"{index}={csv(i32_bits(v) for v in values)}"]
    if dump_main:
        result.append("--dump-main")
    return result


def native_main() -> bytes:
    process = one.invoke(command(dump_main=True))
    status, values = one.parse_output(process)
    if status != "OK" or values != ORACLE_BITS:
        raise RuntimeError(
            f"six-load native control failed: status={status} values={values}\n"
            f"{process.stdout}\n{process.stderr}")
    for line in process.stdout.splitlines():
        if line.startswith("MAIN_ORIG "):
            return bytes.fromhex(line.split(maxsplit=1)[1])
    raise RuntimeError("agxtest did not report MAIN_ORIG")


def locate_falu2i(main: bytes) -> list[tuple[int, dict]]:
    import sys

    sys.path.insert(0, str(ROOT / "agx-isa"))
    import isadb  # pylint: disable=import-error,import-outside-toplevel

    records, leftover = isadb.disassemble(main)
    if leftover:
        raise RuntimeError(f"decoder left {len(leftover)} trailing bytes")
    offset = 0
    located = []
    for record in records:
        if record["mnemonic"] == "falu2i":
            located.append((offset, record))
        offset += record["length"]
    if len(located) != 6:
        raise RuntimeError(f"expected six FALU2I instructions, got {len(located)}")
    selectors = tuple(record["fields"]["mods"] >> 5 for _, record in located)
    if selectors != EXPECTED_NATIVE_SELECTORS:
        raise RuntimeError(
            f"native selector order changed: {selectors} != "
            f"{EXPECTED_NATIVE_SELECTORS}")
    return located


def execute(main: bytes, offset: int, native_selector: int,
            selector: int) -> dict:
    process = one.invoke(command() + [
        "--splice", one.consumer_splice(main, offset, selector)])
    status, values = one.parse_output(process)
    return {
        "consumer_offset": offset,
        "native_selector": native_selector,
        "candidate_selector": selector,
        "relation": "matching" if native_selector == selector else "mismatched",
        "status": status,
        "values": values,
        "oracle": ORACLE_BITS,
        "exact": status == "OK" and values == ORACLE_BITS,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def main() -> int:
    WORK.mkdir(exist_ok=True)
    native = native_main()
    consumers = locate_falu2i(native)
    orders = (
        ("forward", [(entry, selector) for entry in consumers
                     for selector in range(8)]),
        ("reverse", [(entry, selector) for entry in reversed(consumers)
                     for selector in range(7, -1, -1)]),
    )
    passes = []
    for pass_name, cases in orders:
        records = []
        for (offset, record), selector in cases:
            native_selector = record["fields"]["mods"] >> 5
            result = execute(native, offset, native_selector, selector)
            records.append(result)
            print(
                f"{pass_name:7} offset={offset:#04x} native={native_selector} "
                f"candidate={selector} exact={int(result['exact'])} "
                f"status={result['status']}", flush=True)
        passes.append({"name": pass_name, "records": records})

    payload = {
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "native_main_hex": native.hex(),
        "native_selectors": list(EXPECTED_NATIVE_SELECTORS),
        "oracle_bits": ORACLE_BITS,
        "passes": passes,
    }
    (ROOT / "NATIVE_SIX_RESULTS.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")

    all_records = [record for p in passes for record in p["records"]]
    matching = [record for record in all_records if record["relation"] == "matching"]
    mismatched = [record for record in all_records if record["relation"] == "mismatched"]
    passed = all(record["exact"] for record in matching) and \
        not any(record["exact"] for record in mismatched)
    print(
        f"SUMMARY records={len(all_records)} matching_exact="
        f"{sum(r['exact'] for r in matching)}/{len(matching)} "
        f"mismatched_exact={sum(r['exact'] for r in mismatched)}/"
        f"{len(mismatched)} pass={int(passed)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
