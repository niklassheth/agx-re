#!/usr/bin/env python3
"""Cross producer-slot tags with bits 12--17 in several consumer families."""

from __future__ import annotations

import json
import pathlib
import subprocess
import time

import run_remote as common


ROOT = pathlib.Path(__file__).resolve().parent
TOKENS = {
    1: "1100",
    2: "5100",
    3: "9100",
    4: "d100",
    5: "1101",
    6: "5101",
}

# Byte offsets of the two-byte producer-token words within _agc.main.  IMAD's
# three inputs are intentionally retagged as one group, matching native Metal.
LOAD_TOKEN_OFFSETS = {
    "u2f_load": (0x0C,),
    "reciprocal_load": (0x0C,),
    "popcount_load": (0x0C,),
    "extract_load": (0x0C,),
    "imad_load": (0x0C, 0x1A, 0x28),
    "iadd_load": (0x0C, 0x1A),
    "isub_load": (0x0C, 0x1A),
}


def main_bytes(function: str, spec: dict) -> bytes:
    archive = ROOT / "consumers" / f"{function}.archive.bin"
    command = [
        "python3", str(common.AGXTEST),
        "--source", str(common.SOURCE), "--function", function,
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(archive), "--workdir", str(common.WORK),
        "--out", "0=4", "--run-timeout", "15", "--dump-main",
    ]
    for index, values in spec["buffers"].items():
        command += ["--buf", f"{index}={common.signed_csv(values)}"]
    process = subprocess.run(
        command, text=True, capture_output=True, timeout=25, check=False)
    return bytes.fromhex(next(
        line.split(maxsplit=1)[1] for line in process.stdout.splitlines()
        if line.startswith("MAIN_ORIG ")))


def execute(function: str, spec: dict, splices: list[str]) -> dict:
    archive = ROOT / "consumers" / f"{function}.archive.bin"
    command = [
        "python3", str(common.AGXTEST),
        "--source", str(common.SOURCE), "--function", function,
        "--grid", "4", "--tg", "4", "--int",
        "--archive", str(archive), "--workdir", str(common.WORK),
        "--out", "0=4", "--run-timeout", "15",
    ]
    for index, values in spec["buffers"].items():
        command += ["--buf", f"{index}={common.signed_csv(values)}"]
    for splice in splices:
        command += ["--splice", splice]
    started = time.monotonic()
    process = subprocess.run(
        command, text=True, capture_output=True, timeout=25, check=False)
    status, values = common.parse(process.stdout)
    return {
        "status": status,
        "values": values,
        "exact": status == "OK" and values == spec["oracle"],
        "returncode": process.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def field_splice(offset: int, native: bytes, mask: int) -> str:
    field = common.encode_field(mask, native[offset + 1], native[offset + 2])
    return f"_agc.main@{offset + 1:#x}={field.hex()}"


def main() -> int:
    common.WORK.mkdir(exist_ok=True)
    records = []
    for function, token_offsets in LOAD_TOKEN_OFFSETS.items():
        spec = common.CASES[function]
        native = main_bytes(function, spec)
        consumer = spec["consumer"]
        for producer_slot, token in TOKENS.items():
            correct_mask = 1 << (producer_slot - 1)
            wrong_slot = (producer_slot % 6) + 1
            for relation, mask in (
                    ("matching", correct_mask),
                    ("neighbor", 1 << (wrong_slot - 1)),
                    ("matching_plus_neighbor",
                     correct_mask | (1 << (wrong_slot - 1)))):
                splices = [f"_agc.main@{offset:#x}={token}"
                           for offset in token_offsets]
                splices.append(field_splice(consumer, native, mask))
                result = execute(function, spec, splices)
                record = {
                    "kind": "device_load_cross",
                    "function": function,
                    "producer_slot": producer_slot,
                    "consumer_mask": mask,
                    "relation": relation,
                    **result,
                }
                records.append(record)
                print(f"{function:16} producer={producer_slot} "
                      f"mask={mask:02x} {relation:22} "
                      f"exact={int(result['exact'])} values={result['values']}",
                      flush=True)

    # GET_SR uses suffix values 0x06..0xa6 in native programs.  Cross those
    # values with the same consumer field.  This deliberately tests whether
    # the suffix is a real pending-slot producer tag or merely correlated
    # compiler state.
    function = "sys_u2f"
    spec = {
        "consumer": 0x04,
        "buffers": {0: [0] * 4},
        "oracle": [0, 1_065_353_216, 1_073_741_824, 1_077_936_128],
    }
    native = main_bytes(function, spec)
    for suffix_slot in range(1, 7):
        suffix = 0x06 + 0x20 * (suffix_slot - 1)
        for consumer_slot in range(0, 7):
            mask = 0 if consumer_slot == 0 else 1 << (consumer_slot - 1)
            splices = [
                f"_agc.main@0x3={suffix:02x}",
                field_splice(spec["consumer"], native, mask),
            ]
            result = execute(function, spec, splices)
            records.append({
                "kind": "get_sr_cross",
                "function": function,
                "suffix_slot": suffix_slot,
                "consumer_slot": consumer_slot,
                "consumer_mask": mask,
                **result,
            })
            print(f"{function:16} suffix={suffix_slot} consumer={consumer_slot} "
                  f"exact={int(result['exact'])} values={result['values']}",
                  flush=True)

    payload = {
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "records": records,
    }
    (ROOT / "CROSS_RESULTS.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"SUMMARY records={len(records)} "
          f"exact={sum(record['exact'] for record in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
