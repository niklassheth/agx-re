#!/usr/bin/env python3
"""Compile and execute own-source T8132 atomic probes with exact oracles."""

import argparse
import json
import math
from pathlib import Path
import struct
import subprocess


MASK = 0xffffffff
LANES = 16
U_INIT = [(0x80000000 ^ (i * 0x010203)) & MASK for i in range(LANES)]
U_VALUE = [(i * 7 + 3) & MASK for i in range(LANES)]
S_INIT = [-100 + i * 13 for i in range(LANES)]
S_VALUE = [50 - i * 7 for i in range(LANES)]
COUNT = [0, 1, 2, 3, 4, 5, 7, 8, 11, 13, 16, 19, 23, 29, 31, 37]
FUNCTIONS = [
    "dev_add", "dev_sub", "dev_and", "dev_or", "dev_xor", "dev_umin",
    "dev_umax", "dev_xchg", "dev_imin", "dev_imax", "dev_cmpxchg",
    "dev_noret", "dev_return_fanout", "dev_dynamic_index", "dev_loop",
    "dev_if", "dev_contended_add", "tg_contended_add", "tg_ops",
    "tg_cmpxchg", "dev_fadd",
]


def u32(x):
    return x & MASK


def s32(x):
    x &= MASK
    return x - (1 << 32) if x & (1 << 31) else x


def pack_u32(values):
    return b"".join(struct.pack("<I", u32(value)) for value in values)


def pack_f32(values):
    return b"".join(struct.pack("<f", value) for value in values)


def fbits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def compile_archive(shdump, source, function, path):
    proc = subprocess.run(
        [str(shdump), "-o", str(path), "-f", function, "--no-fast-math",
         str(source)], capture_output=True, text=True, timeout=90)
    if proc.returncode:
        raise RuntimeError(f"shdump {function}:\n{proc.stdout}\n{proc.stderr}")


def execute(agxrun, source, function, archive, inputs, output_size, workdir):
    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--no-fast-math", "--grid", str(LANES),
           "--tg", str(LANES)]
    for index, path in sorted(inputs.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", f"0={output_size}"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                              cwd=workdir)
    except subprocess.TimeoutExpired:
        return {"status": "HANG"}
    status, raw = None, None
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            raw = bytes.fromhex(line.split(None, 2)[2])
    row = {"status": status or f"EXIT_{proc.returncode}",
           "stdout": proc.stdout, "stderr": proc.stderr}
    if raw is not None:
        row["words"] = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    return row


def indexed_expected(name):
    if name in ("dev_imin", "dev_imax"):
        initial = [u32(x) for x in S_INIT]
        value = [u32(x) for x in S_VALUE]
    else:
        initial, value = U_INIT, U_VALUE
    tags = {
        "dev_add": 0x10000000, "dev_sub": 0x11000000,
        "dev_and": 0x12000000, "dev_or": 0x13000000,
        "dev_xor": 0x14000000, "dev_umin": 0x15000000,
        "dev_umax": 0x16000000, "dev_xchg": 0x17000000,
        "dev_imin": 0x18000000, "dev_imax": 0x19000000,
    }
    result = []
    for lane, (old, operand) in enumerate(zip(initial, value)):
        if name == "dev_add":
            now = u32(old + operand)
        elif name == "dev_sub":
            now = u32(old - operand)
        elif name == "dev_and":
            now = old & operand
        elif name == "dev_or":
            now = old | operand
        elif name == "dev_xor":
            now = old ^ operand
        elif name == "dev_umin":
            now = min(old, operand)
        elif name == "dev_umax":
            now = max(old, operand)
        elif name == "dev_imin":
            now = u32(min(s32(old), s32(operand)))
        elif name == "dev_imax":
            now = u32(max(s32(old), s32(operand)))
        elif name == "dev_xchg":
            now = operand
        result.extend((old, now, operand, tags[name] | lane))
    return result


def case_inputs(name, workdir):
    def write(index, stem, raw):
        path = (workdir / f"{name}_{stem}.bin").resolve()
        path.write_bytes(raw)
        inputs[index] = path

    inputs = {}
    output_size = LANES * 16
    if name in ("dev_imin", "dev_imax"):
        write(1, "target", pack_u32(S_INIT))
        write(2, "value", pack_u32(S_VALUE))
        want = indexed_expected(name)
    elif name in {"dev_add", "dev_sub", "dev_and", "dev_or", "dev_xor",
                  "dev_umin", "dev_umax", "dev_xchg"}:
        write(1, "target", pack_u32(U_INIT))
        write(2, "value", pack_u32(U_VALUE))
        want = indexed_expected(name)
    elif name == "dev_cmpxchg":
        pairs, want = [], []
        for lane, old in enumerate(U_INIT):
            expected = old if lane % 2 == 0 else u32(old + 1)
            desired = 0x90000000 | lane
            pairs.extend((expected, desired))
            success = lane % 2 == 0
            observed = expected if success else old
            now = desired if success else old
            want.extend((observed, now, int(success), 0x1a000000 | lane))
        write(1, "target", pack_u32(U_INIT))
        write(2, "pairs", pack_u32(pairs))
    elif name == "dev_noret":
        write(1, "target", pack_u32(U_INIT))
        write(2, "value", pack_u32(U_VALUE))
        want = []
        for lane, (old, value) in enumerate(zip(U_INIT, U_VALUE)):
            want.extend((u32(old + value), value, lane ^ 0x55,
                         0x1b000000 | lane))
    elif name == "dev_return_fanout":
        write(1, "target", pack_u32(U_INIT))
        write(2, "value", pack_u32(U_VALUE))
        want = []
        for lane, (old, value) in enumerate(zip(U_INIT, U_VALUE)):
            want.extend((u32(old + 0x10203), old ^ 0xa5a5a5a5,
                         old ^ value, 0x1c000000 | lane))
    elif name == "dev_dynamic_index":
        permutation = [15 - lane for lane in range(LANES)]
        pairs, want = [], []
        for lane, index in enumerate(permutation):
            value = U_VALUE[lane]
            pairs.extend((index, value))
            want.extend((U_INIT[index], index, value, index * 17 + value))
        write(1, "target", pack_u32(U_INIT))
        write(2, "pairs", pack_u32(pairs))
    elif name == "dev_loop":
        write(1, "target", pack_u32(U_INIT))
        write(2, "count", pack_u32(COUNT))
        want = []
        for lane, (old, count) in enumerate(zip(U_INIT, COUNT)):
            last = 0 if count == 0 else u32(old + count * (count - 1) // 2)
            now = u32(old + count * (count + 1) // 2)
            want.extend((last, now, count, 0x1d000000 | lane))
    elif name == "dev_if":
        write(1, "target", pack_u32(U_INIT))
        write(2, "value", pack_u32(U_VALUE))
        want = []
        for lane, (old, value) in enumerate(zip(U_INIT, U_VALUE)):
            active = ((lane ^ value) & 1) != 0
            want.extend((old if active else 0xeeeeeeee,
                         old | value if active else old, value,
                         0x1e000000 | lane))
    elif name == "dev_contended_add":
        write(1, "target", pack_u32([100]))
        output_size = 17 * 4
        want = list(range(100, 116)) + [116]
    elif name == "tg_contended_add":
        output_size = 17 * 4
        want = list(range(16)) + [16]
    elif name == "tg_ops":
        write(1, "input", pack_u32(U_VALUE))
        want = []
        for lane in range(LANES):
            want.extend((100 + lane, 0xf0f0 ^ lane, 100 + lane, 100 + lane))
    elif name == "tg_cmpxchg":
        pairs, want = [], []
        for lane in range(LANES):
            old = 0x7000 + lane
            expected = old if lane % 2 == 0 else old + 1
            desired = 0xa000 + lane
            pairs.extend((expected, desired))
            success = lane % 2 == 0
            want.extend((expected if success else old,
                         desired if success else old, int(success),
                         0x20000000 | lane))
        write(1, "pairs", pack_u32(pairs))
    elif name == "dev_fadd":
        initial = [float(lane) + 0.25 for lane in range(LANES)]
        values = [float((lane % 5) + 1) * 0.5 for lane in range(LANES)]
        write(1, "target", pack_f32(initial))
        write(2, "value", pack_f32(values))
        want = []
        for lane, (old, value) in enumerate(zip(initial, values)):
            want.extend((fbits(old), fbits(old + value), fbits(value),
                         0x1f000000 | lane))
    else:
        raise KeyError(name)
    return inputs, output_size, want


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shdump", type=Path, required=True)
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("atomic_semantics.metal"))
    ap.add_argument("--workdir", type=Path, default=Path("work/native"))
    ap.add_argument("--output", type=Path, default=Path("raw/native_results.json"))
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    archives = args.workdir / "archives"
    archives.mkdir(exist_ok=True)

    results = {}
    for function in FUNCTIONS:
        inputs, output_size, want = case_inputs(function, args.workdir)
        archive = (archives / f"{function}.bin").resolve()
        compile_archive(args.shdump.resolve(), args.source.resolve(), function,
                        archive)
        row = execute(args.agxrun.resolve(), args.source.resolve(), function,
                      archive, inputs, output_size, args.workdir.resolve())
        got = row.get("words")
        if function in ("dev_contended_add", "tg_contended_add") and got:
            got = sorted(got[:16]) + got[16:]
        row["expected"] = want
        row["verdict"] = "MATCH" if got == want else "MISMATCH"
        results[function] = row
        print(f"{function:24s} {row['status']:14s} {row['verdict']}")
        if row["verdict"] != "MATCH":
            print("  got     ", got)
            print("  expected", want)

    args.output.write_text(json.dumps(results, indent=2) + "\n")
    if not all(row["verdict"] == "MATCH" for row in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
