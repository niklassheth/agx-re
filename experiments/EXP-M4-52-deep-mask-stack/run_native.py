#!/usr/bin/env python3
"""Compile and execute the native deep-mask nesting ladder."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from generate import DEPTHS, LANES, MAX_DEPTH, STRIDE, source


MASK = 0xffffffff
PATHS = [
    0xffffffff, 0x00000000, 0xaaaaaaaa, 0x55555555,
    0x0001, 0x0003, 0x007f, 0x00ff,
    0x0100, 0x01ff, 0x0f0f, 0xf00f,
    0x0000ffff, 0x00010000, 0x7fffffff, 0x80000000,
]
SALTS = [
    0x01020304, 0x11223344, 0xdeadbeef, 0x00000000,
    0x00000001, 0x00000007, 0x00000013, 0xffffffff,
    0x80000000, 0x7fffffff, 0x13579bdf, 0x2468ace0,
    0x89abcdef, 0x76543210, 0xa5a5a5a5, 0x5a5a5a5a,
]


def u32(value):
    return value & MASK


def poison(lane, word):
    return u32(0xc001d00d ^ (lane * 0x01010101) ^ (word * 0x9e3779b9))


def expected(depth):
    result = [poison(lane, word) for lane in range(LANES)
              for word in range(STRIDE)]
    for lane in range(LANES):
        base = lane * STRIDE
        path = PATHS[lane]
        value = SALTS[lane] ^ (0x0badc000 | depth)
        visited = 0
        entered = True
        active_levels = []
        for level in range(depth):
            if not entered:
                break
            trace = 4 + 2 * level
            bit = 1 << level
            if path & bit:
                value = u32(value * (3 + 2 * level) +
                            0x10203041 + level * 0x01010101)
                result[base + trace] = value ^ (0x40000000 | level)
                visited |= bit
                active_levels.append(level)
            else:
                value ^= 0x81020408 ^ (level * 0x00110101)
                result[base + trace] = value ^ (0x60000000 | level)
                value = u32(value + 0x31415927 + level * 0x00010003)
                result[base + trace + 1] = value ^ (0x70000000 | level)
                entered = False
        for level in reversed(active_levels):
            trace = 4 + 2 * level
            value = u32(value * (5 + 2 * level) +
                        0x21314151 + level * 0x000f0103)
            result[base + trace + 1] = value ^ (0x50000000 | level)
        result[base + 0] = value
        result[base + 1] = visited
        result[base + 2] = path
        result[base + 3] = 0xd0000000 | depth
    return result


def pack_u32(values):
    return b"".join(struct.pack("<I", value) for value in values)


def run_command(cmd, timeout, cwd=None):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, cwd=cwd)
        return {"returncode": proc.returncode, "stdout": proc.stdout,
                "stderr": proc.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None, "stdout": exc.stdout or "",
                "stderr": exc.stderr or "", "timeout": True}


def compile_one(shdump, source_path, function, archive):
    row = run_command([str(shdump), "-o", str(archive), "-f", function,
                       "--no-fast-math", str(source_path)], 120)
    if archive.exists():
        raw = archive.read_bytes()
        row.update({"archive_size": len(raw),
                    "archive_sha256": hashlib.sha256(raw).hexdigest()})
    return row


def execute_one(agxrun, source_path, function, archive, inputs, output_size,
                cwd):
    cmd = [str(agxrun), "--archive", str(archive), "--source",
           str(source_path), "--function", function, "--no-fast-math",
           "--grid", str(LANES), "--tg", str(LANES)]
    for index, path in sorted(inputs.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", f"0={output_size}"]
    row = run_command(cmd, 30, cwd)
    status = None
    raw = None
    for line in row["stdout"].splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            raw = bytes.fromhex(line.split(None, 2)[2])
    row["status"] = "HANG" if row.get("timeout") else (
        status or f"EXIT_{row['returncode']}")
    if raw is not None:
        row["words"] = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shdump", type=Path, required=True)
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("deep_mask_stack.metal"))
    ap.add_argument("--workdir", type=Path, default=Path("work/native"))
    ap.add_argument("--output", type=Path,
                    default=Path("raw/native_results.json"))
    ap.add_argument("--compile-only", action="store_true")
    ap.add_argument("--runs", type=int, default=2)
    args = ap.parse_args()

    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source_path = args.source.resolve()
    source_path.write_text(source())
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()

    paths_file = (args.workdir / "paths.bin").resolve()
    salts_file = (args.workdir / "salts.bin").resolve()
    paths_file.write_bytes(pack_u32(PATHS))
    salts_file.write_bytes(pack_u32(SALTS))

    results = {"metadata": {"source_sha256": source_hash,
                             "depths": DEPTHS, "lanes": LANES,
                             "stride_words": STRIDE},
               "compile_orders": {}, "execution": {}}
    for order_name, depths in (("forward", DEPTHS),
                               ("reverse", tuple(reversed(DEPTHS)))):
        archive_dir = args.workdir / f"archives-{order_name}"
        archive_dir.mkdir(exist_ok=True)
        order_rows = {}
        for depth in depths:
            function = f"nested_{depth}"
            archive = (archive_dir / f"{function}.bin").resolve()
            row = compile_one(args.shdump.resolve(), source_path, function,
                              archive)
            row["status"] = "COMPILED" if row["returncode"] == 0 else (
                "HANG" if row.get("timeout") else "REJECTED")
            order_rows[function] = row
            print(f"{order_name:7s} {function:10s} {row['status']}")
        results["compile_orders"][order_name] = order_rows

    if not args.compile_only:
        output_bytes = LANES * STRIDE * 4
        for depth in DEPTHS:
            function = f"nested_{depth}"
            compile_row = results["compile_orders"]["forward"][function]
            if compile_row["status"] != "COMPILED":
                results["execution"][function] = []
                continue
            want = expected(depth)
            runs = []
            for run in range(args.runs):
                seeded = (args.workdir / f"seed-{function}-{run}.bin").resolve()
                seeded.write_bytes(pack_u32(
                    poison(lane, word) for lane in range(LANES)
                    for word in range(STRIDE)))
                archive = (args.workdir / "archives-forward" /
                           f"{function}.bin").resolve()
                row = execute_one(args.agxrun.resolve(), source_path, function,
                                  archive, {0: seeded, 1: paths_file,
                                            2: salts_file}, output_bytes,
                                  args.workdir.resolve())
                row["verdict"] = "MATCH" if row.get("words") == want else "MISMATCH"
                if row["verdict"] == "MISMATCH" and row.get("words"):
                    row["first_difference"] = next(
                        ({"word": i, "got": got, "expected": exp}
                         for i, (got, exp) in enumerate(zip(row["words"], want))
                         if got != exp), None)
                runs.append(row)
                print(f"execute {function:10s} run{run + 1} "
                      f"{row['status']:14s} {row['verdict']}")
            results["execution"][function] = runs

    args.output.write_text(json.dumps(results, indent=2) + "\n")
    compilation_ok = all(
        row["status"] == "COMPILED"
        for order in results["compile_orders"].values()
        for row in order.values())
    execution_ok = args.compile_only or all(
        row["status"] == "OK" and row["verdict"] == "MATCH"
        for runs in results["execution"].values() for row in runs)
    if not compilation_ok or not execution_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
