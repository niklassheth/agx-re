#!/usr/bin/env python3
"""Execute the retained atomic-result fanout S x R matrix."""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
from pathlib import Path


LANES = 32
MASK = 0xFFFFFFFF


def pack_u32(values):
    return b"".join(struct.pack("<I", value & MASK) for value in values)


def execute(agxrun: Path, archive: Path, source: Path, workdir: Path):
    target = workdir / "target.bin"
    operand = workdir / "operand.bin"
    initial = [(0x6A000000 + lane * 0x10203) & MASK for lane in range(LANES)]
    values = [(0x13579BDF ^ (lane * 0x11011)) & MASK for lane in range(LANES)]
    target.write_bytes(pack_u32(initial))
    operand.write_bytes(pack_u32(values))
    command = [str(agxrun.resolve()), "--archive", str(archive.resolve()),
               "--source", str(source.resolve()), "--function",
               "atomic_pending_fanout", "--no-fast-math",
               "--grid", str(LANES), "--tg", str(LANES),
               "--buf", f"1={target.resolve()}",
               "--buf", f"2={operand.resolve()}",
               "--out", f"0={LANES * 5 * 4}"]
    try:
        proc = subprocess.run(command, cwd=workdir, capture_output=True,
                              text=True, timeout=12)
    except subprocess.TimeoutExpired:
        return {"status": "HANG", "verdict": "HANG"}
    status, raw = None, None
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            raw = bytes.fromhex(line.split(None, 2)[2])
    words = (list(struct.unpack(f"<{len(raw) // 4}I", raw))
             if raw is not None else None)
    expected = []
    for before, value in zip(initial, values):
        expected.extend((before, before, (before + 0x10203) & MASK,
                         value, before ^ value))
    return {"status": status or f"EXIT_{proc.returncode}",
            "verdict": "MATCH" if words == expected else "MISMATCH",
            "words": words, "expected": expected,
            "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agxrun", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=2)
    args = parser.parse_args()
    manifest = json.loads((args.directory / "manifest.json").read_text())
    by_name = {row["archive"]: row for row in manifest}
    workdir = args.output.parent / "fanout_run_work"
    workdir.mkdir(parents=True, exist_ok=True)
    rows = []
    for sequence, name in enumerate(
            name for row in manifest for name in [row["archive"]] * args.repeats):
        result = execute(args.agxrun, args.directory / name, args.source,
                         workdir)
        result.update(by_name[name])
        result["sequence"] = sequence
        rows.append(result)
        print(f"{sequence:03d} {name:18s} {result['status']:14s} "
              f"{result['verdict']}", flush=True)
        if len(rows) >= 2 and all(r["verdict"] == "HANG" for r in rows[-2:]):
            break
    args.output.write_text(json.dumps(rows, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
