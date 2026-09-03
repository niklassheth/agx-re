#!/usr/bin/env python3
"""Same-boot control proving the EXP-M4-42 producer tags remain functional."""

from __future__ import annotations

import json
import pathlib

import run_remote as falu


ROOT = pathlib.Path(__file__).resolve().parent
SOURCE = ROOT / "wide_control.metal"
WORK = ROOT / "work-wide"
ARCHIVE = WORK / "u2f_slot_control.archive.bin"
INPUTS = [0, 1, 7, 16_777_215]
ORACLE = [0, 1_065_353_216, 1_088_421_888, 1_266_679_807]


def csv(values) -> str:
    return ",".join(str(value) for value in values)


def command(*, dump_main: bool = False) -> list[str]:
    result = [
        "python3", str(falu.AGXTEST),
        "--source", str(SOURCE), "--function", "u2f_slot_control",
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(ARCHIVE), "--workdir", str(WORK),
        "--buf", "0=0,0,0,0", "--buf", f"1={csv(INPUTS)}",
        "--out", "0=4", "--run-timeout", "15",
    ]
    if dump_main:
        result.append("--dump-main")
    return result


def locate(main: bytes) -> tuple[int, int]:
    import sys

    sys.path.insert(0, str(ROOT / "agx-isa"))
    import isadb  # pylint: disable=import-error,import-outside-toplevel

    records, leftover = isadb.disassemble(main)
    if leftover:
        raise RuntimeError(f"decoder left {len(leftover)} bytes")
    offset = 0
    load_offsets = []
    consumer_offsets = []
    for record in records:
        if record["mnemonic"] == "device_load":
            load_offsets.append(offset)
        if record["mnemonic"] == "cvt_i2f":
            consumer_offsets.append(offset)
        offset += record["length"]
    if len(load_offsets) != 1 or len(consumer_offsets) != 1:
        raise RuntimeError(
            f"expected one load/conversion, got {load_offsets}/{consumer_offsets}")
    return load_offsets[0], consumer_offsets[0]


def encode_mask(main: bytes, offset: int, mask: int) -> str:
    b1 = (main[offset + 1] & 0x0F) | ((mask & 0x0F) << 4)
    b2 = (main[offset + 2] & 0xFC) | ((mask >> 4) & 0x03)
    return f"_agc.main@{offset + 1:#x}={b1:02x}{b2:02x}"


def main() -> int:
    WORK.mkdir(exist_ok=True)
    process = falu.invoke(command(dump_main=True))
    status, values = falu.parse_output(process)
    if status != "OK" or values != ORACLE:
        raise RuntimeError(f"native wide control failed: {status} {values}")
    main_hex = next(line.split(maxsplit=1)[1]
                    for line in process.stdout.splitlines()
                    if line.startswith("MAIN_ORIG "))
    native = bytes.fromhex(main_hex)
    load_offset, consumer_offset = locate(native)

    records = []
    for producer_slot, token in falu.TOKENS.items():
        neighbor = (producer_slot % 6) + 1
        for relation, consumer_slot in (
                ("matching", producer_slot), ("neighbor", neighbor)):
            mask = 1 << (consumer_slot - 1)
            cmd = command() + [
                "--splice", f"_agc.main@{load_offset + 8:#x}={token}",
                "--splice", encode_mask(native, consumer_offset, mask),
            ]
            run = falu.invoke(cmd)
            run_status, run_values = falu.parse_output(run)
            exact = run_status == "OK" and run_values == ORACLE
            record = {
                "producer_slot": producer_slot,
                "consumer_slot": consumer_slot,
                "relation": relation,
                "status": run_status,
                "values": run_values,
                "oracle": ORACLE,
                "exact": exact,
                "returncode": run.returncode,
                "stdout": run.stdout,
                "stderr": run.stderr,
            }
            records.append(record)
            print(f"wide producer={producer_slot} consumer={consumer_slot} "
                  f"{relation} exact={int(exact)} values={run_values}", flush=True)

    payload = {
        "schema_version": 1,
        "native_main_hex": native.hex(),
        "load_offset": load_offset,
        "consumer_offset": consumer_offset,
        "records": records,
    }
    (ROOT / "WIDE_CONTROL_RESULTS.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    matching = [r for r in records if r["relation"] == "matching"]
    neighbor = [r for r in records if r["relation"] == "neighbor"]
    passed = all(r["exact"] for r in matching) and not any(r["exact"] for r in neighbor)
    print(f"SUMMARY matching_exact={sum(r['exact'] for r in matching)}/6 "
          f"neighbor_exact={sum(r['exact'] for r in neighbor)}/6 pass={int(passed)}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
