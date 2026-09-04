#!/usr/bin/env python3
"""Execute patched native archives with exact atomic output oracles on macOS."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path


MASK = 0xFFFFFFFF
LANES = 16
U_INIT = [(0x80000000 ^ (i * 0x010203)) & MASK for i in range(LANES)]
U_VALUE = [(i * 7 + 3) & MASK for i in range(LANES)]


def pack_u32(values):
    return b"".join(struct.pack("<I", value & MASK) for value in values)


def dev_add_expected():
    result = []
    for lane, (old, operand) in enumerate(zip(U_INIT, U_VALUE)):
        result.extend((old, (old + operand) & MASK, operand,
                       0x10000000 | lane))
    return result


def execute(agxrun: Path, archive: Path, source: Path, function: str,
            workdir: Path):
    agxrun = agxrun.resolve()
    archive = archive.resolve()
    source = source.resolve()
    inputs = {}
    if function == "dev_contended_add":
        target = workdir / "contended_target.bin"
        target.write_bytes(pack_u32([100]))
        inputs[1] = target.resolve()
        output_size = 17 * 4
        expected = list(range(100, 116)) + [116]
    elif function == "dev_add":
        target = workdir / "dev_add_target.bin"
        value = workdir / "dev_add_value.bin"
        target.write_bytes(pack_u32(U_INIT))
        value.write_bytes(pack_u32(U_VALUE))
        inputs = {1: target.resolve(), 2: value.resolve()}
        output_size = LANES * 16
        expected = dev_add_expected()
    else:
        raise ValueError(function)

    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--no-fast-math", "--grid", str(LANES),
           "--tg", str(LANES)]
    for binding, path in sorted(inputs.items()):
        cmd += ["--buf", f"{binding}={path}"]
    cmd += ["--out", f"0={output_size}"]
    try:
        proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True,
                              timeout=12)
    except subprocess.TimeoutExpired:
        return {"status": "HANG", "verdict": "HANG"}

    status = None
    raw = None
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            raw = bytes.fromhex(line.split(None, 2)[2])
    words = (list(struct.unpack(f"<{len(raw) // 4}I", raw))
             if raw is not None else None)
    compared = words
    if function == "dev_contended_add" and words is not None:
        compared = sorted(words[:16]) + words[16:]
    return {
        "status": status or f"EXIT_{proc.returncode}",
        "verdict": "MATCH" if compared == expected else "MISMATCH",
        "words": words,
        "expected": expected,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--directory", type=Path, required=True)
    ap.add_argument("--family", choices=("compact", "long"), required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--desc-start", type=lambda value: int(value, 0), default=0)
    ap.add_argument("--desc-end", type=lambda value: int(value, 0), default=255)
    args = ap.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    workdir = args.output.parent / f"{args.family}_run_work"
    workdir.mkdir(parents=True, exist_ok=True)
    rows = []
    consecutive_hangs = 0
    archives = sorted(args.directory.glob(f"{args.family}_*.bin"))
    filtered = []
    for archive in archives:
        marker = f"{args.family}_desc_"
        if archive.stem.startswith(marker):
            value = int(archive.stem[len(marker):], 16)
            if not (args.desc_start <= value <= args.desc_end):
                continue
        elif args.desc_start != 0 or args.desc_end != 255:
            continue
        filtered.append(archive)
    archives = filtered
    baseline = args.directory / f"{args.family}_baseline.bin"

    schedule = []
    for index, archive in enumerate(archives):
        schedule.extend([archive] * args.repeats)
        if (index + 1) % 8 == 0:
            schedule.append(baseline)

    for sequence, archive in enumerate(schedule):
        function = ("dev_contended_add" if args.family == "compact"
                    else "dev_add")
        row = execute(args.agxrun, archive, args.source, function, workdir)
        row.update({"sequence": sequence, "archive": archive.name,
                    "family": args.family, "function": function})
        rows.append(row)
        print(f"{sequence:03d} {archive.name:36s} "
              f"{row['status']:14s} {row['verdict']}", flush=True)
        consecutive_hangs = consecutive_hangs + 1 if row["verdict"] == "HANG" else 0
        if consecutive_hangs >= 2:
            print("stopping after two consecutive hangs", flush=True)
            break

    args.output.write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
