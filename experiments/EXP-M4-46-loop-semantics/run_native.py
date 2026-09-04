#!/usr/bin/env python3
"""Compile and execute the own-source T8132 loop matrix."""

import argparse
import json
from pathlib import Path
import struct
import subprocess


MASK = 0xffffffff
COUNT = [0, 1, 2, 3, 4, 5, 7, 8, 11, 13, 16, 19, 23, 29, 31, 37]
AUX = [0x01020304, 0x11223344, 0xdeadbeef, 0, 1, 7, 19, 0xffffffff,
       0x80000000, 0x7fffffff, 0x13579bdf, 0x2468ace0, 3, 5, 11, 17]
CUT = [0, 9, 1, 7, 2, 99, 5, 3, 11, 4, 32, 8, 0, 27, 6, 36]
INNER = [0, 1, 2, 3, 4, 5, 1, 6, 2, 7, 3, 4, 8, 2, 5, 1]

FUNCTIONS = [
    "while_top", "do_bottom", "for_dynamic", "loop_break",
    "loop_continue", "if_inside_loop", "loop_inside_if", "nested_loops",
    "carried_pair", "carried_vector", "nested_break_continue",
    "pc_base_probe", "infinite_break", "loop_device_load",
    "compound_latch",
    "break_nested_if", "continue_nested_if", "break_nested_two_if",
    "triple_nested_loops",
]


def u32(x):
    return x & MASK


def step(value, iteration):
    return u32(value * 3 + (iteration ^ 0x35))


def expected(name, lane):
    n, aux, cut, inner = COUNT[lane], AUX[lane], CUT[lane], INNER[lane]
    if name in ("while_top", "for_dynamic"):
        tag = 0x10000000 if name == "while_top" else 0x30000000
        seed = 0x10203040 if name == "while_top" else 0x30405060
        value = aux ^ seed
        for i in range(n):
            value = step(value, i)
        return value, n, n, tag | lane
    if name == "do_bottom":
        value = aux ^ 0x20304050
        iterations = max(n, 1)
        for i in range(iterations):
            value = step(value, i)
        return value, iterations, n, 0x20000000 | lane
    if name == "loop_break":
        value, executed, i = 0x40506070 ^ lane, 0, 0
        while i < n:
            if i == cut:
                break
            value = step(value, i)
            executed += 1
            i += 1
        return value, i, executed, 0x40000000 | lane
    if name == "loop_continue":
        value, executed = aux ^ 0x50607080, 0
        for i in range(n):
            if ((i ^ lane) & 3) == 1:
                continue
            value = step(value, i)
            executed += 1
        return value, n, executed, 0x50000000 | lane
    if name == "if_inside_loop":
        value, then_count = aux ^ 0x60708090, 0
        for i in range(n):
            if ((i + lane) & 1) != 0:
                value = step(value, i)
                then_count += 1
            else:
                value = u32(value * 5 - (i | 1))
        return value, n, then_count, 0x60000000 | lane
    if name == "loop_inside_if":
        value, executed = aux ^ 0x708090a0, 0
        if lane & 1:
            for i in range(n):
                value = step(value, i)
                executed += 1
        else:
            value ^= 0x00ff00ff
        return value, n, executed, 0x70000000 | lane
    if name == "nested_loops":
        value, executed = 0x8090a0b0 ^ lane, 0
        for i in range(n):
            for j in range(inner):
                value = step(value, i * 17 + j)
                executed += 1
            value ^= i + 0x91
        return u32(value), n, executed, 0x80000000 | lane
    if name == "carried_pair":
        a, b = aux ^ 0x91a2b3c4, aux ^ 0x4c3b2a19
        for i in range(n):
            a, b = u32(b + i * 3), u32(a ^ (i * 17 + 1))
        return a, b, n, 0x90000000 | lane
    if name == "carried_vector":
        value = [aux, aux ^ 0x11111111, aux ^ 0x22222222,
                 aux ^ 0x33333333]
        mul = [3, 5, 7, 9]
        for i in range(n):
            rotated = value[1:] + value[:1]
            value = [u32(rotated[k] * mul[k] + (i | 1)) for k in range(4)]
        value[3] ^= lane
        return tuple(value)
    if name == "nested_break_continue":
        value, visited = 0xa0b0c0d0 ^ lane, 0
        for i in range(n):
            for j in range(inner):
                if ((i + j + lane) & 3) == 0:
                    continue
                if j == ((lane + 1) & 3):
                    break
                value = step(value, i * 17 + j)
                visited += 1
            value ^= i + 0xb1
        return u32(value), n, visited, 0xa0000000 | lane
    if name == "pc_base_probe":
        value = aux ^ 0xb0c0d0e0
        for i in range(n):
            value = u32(value * 3 + 7)
            value ^= i + 0x123
        return u32(value), n, n, 0xb0000000 | lane
    if name == "infinite_break":
        value = aux ^ 0xc0d0e0f0
        for i in range(n):
            value = step(value, i)
        return value, n, n, 0xc0000000 | lane
    if name == "loop_device_load":
        value = 0xd0e0f001 ^ lane
        for i in range(n):
            value = step(value ^ AUX[(i + lane) & 15], i)
        return value, n, n, 0xd0000000 | lane
    if name == "compound_latch":
        value = aux ^ 0xd1e2f304
        stop = aux & 31
        i = 0
        while i < n and i != stop:
            value = step(value, i)
            i += 1
        return value, i, stop, 0xd1000000 | lane
    if name == "break_nested_if":
        value, executed = 0xe0f00112 ^ lane, 0
        limit = aux & 31
        for i in range(n):
            value = step(value, i)
            executed += 1
            if ((i + lane) & 1) != 0:
                value ^= 0x13570000 + i
                if i == limit:
                    break
                value = u32(value + 0x24680000 + lane)
            else:
                value ^= 0x369a0000 + lane
        return u32(value), executed, n, 0xe0000000 | lane
    if name == "continue_nested_if":
        value, executed, skipped = aux ^ 0xf0011223, 0, 0
        for i in range(n):
            value ^= 0x11110000 + i
            if ((i ^ lane) & 1) != 0:
                value = u32(value + 0x22220000 + lane)
                if ((i + aux) & 3) == 0:
                    skipped += 1
                    continue
                value ^= 0x33330000 + i
            else:
                value = u32(value + 0x44440000 + lane)
            value = step(value, i)
            executed += 1
        return u32(value), executed, skipped, 0xf0000000 | lane
    if name == "break_nested_two_if":
        value, executed = 0x01234567 ^ lane, 0
        limit = aux & 31
        for i in range(n):
            value = step(value, i)
            executed += 1
            if ((i + lane) & 1) != 0:
                value ^= 0x10200000 + i
                if ((i ^ lane) & 2) != 0:
                    value = u32(value + 0x20300000 + lane)
                    if i == limit:
                        break
                    value ^= 0x30400000 + i
                else:
                    value = u32(value + 0x40500000 + lane)
            else:
                value ^= 0x50600000 + lane
        return u32(value), executed, n, 0x01000000 | lane
    if name == "triple_nested_loops":
        value, executed = 0x12345678 ^ lane, 0
        outer = min(n, 3)
        middle = aux & 3
        inner = (aux >> 2) & 3
        for i in range(outer):
            for j in range(middle):
                for k in range(inner):
                    value = step(value, i * 37 + j * 7 + k)
                    executed += 1
                value ^= 0x101 + j
            value = u32(value + 0x10001 + i)
        return u32(value), executed, outer, 0x02000000 | lane
    raise KeyError(name)


def pack_u32(values):
    return b"".join(struct.pack("<I", value) for value in values)


def compile_archive(shdump, source, function, path):
    proc = subprocess.run([str(shdump), "-o", str(path), "-f", function,
                           "--no-fast-math", str(source)],
                          capture_output=True, text=True, timeout=90)
    if proc.returncode:
        raise RuntimeError(f"shdump {function}:\n{proc.stdout}\n{proc.stderr}")


def execute(agxrun, source, function, archive, inputs, workdir):
    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--no-fast-math", "--grid", "16",
           "--tg", "16"]
    for index, path in sorted(inputs.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", "0=256"]
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
    result = {"status": status or f"EXIT_{proc.returncode}",
              "stdout": proc.stdout, "stderr": proc.stderr}
    if raw is not None:
        result["words"] = list(struct.unpack("<64I", raw))
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shdump", type=Path, required=True)
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("loop_semantics.metal"))
    ap.add_argument("--workdir", type=Path, default=Path("work/native"))
    ap.add_argument("--output", type=Path, default=Path("raw/native_results.json"))
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    archives = args.workdir / "archives"
    archives.mkdir(exist_ok=True)

    input_paths = {}
    for index, values in ((1, COUNT), (2, AUX)):
        path = (args.workdir / f"input{index}.bin").resolve()
        path.write_bytes(pack_u32(values))
        input_paths[index] = path

    results = {}
    for function in FUNCTIONS:
        values2 = INNER if function in ("nested_loops", "nested_break_continue") else (
            CUT if function == "loop_break" else AUX)
        path2 = (args.workdir / f"{function}_input2.bin").resolve()
        path2.write_bytes(pack_u32(values2))
        inputs = {1: input_paths[1], 2: path2}
        archive = (archives / f"{function}.bin").resolve()
        compile_archive(args.shdump.resolve(), args.source.resolve(), function, archive)
        row = execute(args.agxrun.resolve(), args.source.resolve(), function,
                      archive, inputs, args.workdir.resolve())
        want = [word for lane in range(16) for word in expected(function, lane)]
        row["expected"] = want
        row["verdict"] = "MATCH" if row.get("words") == want else "MISMATCH"
        results[function] = row
        print(f"{function:24s} {row['status']:14s} {row['verdict']}")
        if row["verdict"] != "MATCH":
            print("  got     ", row.get("words"))
            print("  expected", want)

    args.output.write_text(json.dumps(results, indent=2) + "\n")
    if not all(row["verdict"] == "MATCH" for row in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
