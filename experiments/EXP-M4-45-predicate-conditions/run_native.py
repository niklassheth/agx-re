#!/usr/bin/env python3
"""Run all native predicate/Boolean probes and compare every output lane."""

import argparse
import json
from pathlib import Path
import struct
import subprocess


U = [0, 1, 5, 0xffffffff, 0x80000000, 7, 42, 9,
     16, 15, 31, 32, 0x7fffffff, 2, 100, 3]
V = [1, 0, 5, 0, 0xffffffff, 7, 41, 10,
     15, 16, 32, 31, 0x80000000, 3, 2, 100]
S = [-3, -1, 0, 1, 5, -2147483648, 2147483647, 9,
     -10, 10, -7, 7, 42, -42, 100, 3]
T = [-2, -1, 1, 0, 5, 2147483647, -2147483648, 10,
     10, -10, 7, -7, -42, 42, 2, 100]
F = [-1.0, 1.0, 2.0, 0.0, -0.0, float("inf"), float("-inf"), float("nan"),
     3.5, -2.25, 100.0, 1.0, float("nan"), 7.0, 0.125, -10.0]
G = [1.0, -1.0, 2.0, -0.0, 0.0, float("inf"), float("inf"), 1.0,
     3.25, -2.25, 2.0, float("nan"), float("nan"), 8.0, 0.25, -20.0]
C = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
D = [3, 0, 6, 6, 0, 9, 9, 0, 12, 0, 13, 0, 16, 16, 0, 19]


RELATIONS = {
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
}


def pack(values, kind):
    fmt = {"u": "<I", "s": "<i", "f": "<f"}[kind]
    return b"".join(struct.pack(fmt, value) for value in values)


def run_one(agxrun, archive, source, function, paths, workdir):
    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--grid", "16", "--tg", "16"]
    for index, path in sorted(paths.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", "0=64"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                          cwd=workdir)
    status = None
    raw = None
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            raw = bytes.fromhex(line.split(None, 2)[2])
    if status != "OK" or raw is None:
        raise RuntimeError(f"{function}: status={status}\n{proc.stdout}\n{proc.stderr}")
    return list(struct.unpack("<16I", raw)), proc.stdout, proc.stderr


def direct_expected(name):
    kind, rel = name.split("_")
    lhs, rhs = {"u": (U, V), "s": (S, T), "f": (F, G)}[kind]
    marker = {"u": 0x1000, "s": 0x2000, "f": 0x3000}[kind]
    return [marker + i if RELATIONS[rel](a, b) else 0
            for i, (a, b) in enumerate(zip(lhs, rhs))]


def bool_expected(name):
    if name == "bool_bit_test":
        pred = [(a & 8) != 0 for a in U]
        return [0x4100 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_and":
        pred = [(a < b) and (c != d) for a, b, c, d in zip(U, V, C, D)]
        return [0x4200 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_or":
        pred = [(a < b) or (c == d) for a, b, c, d in zip(U, V, C, D)]
        return [0x4300 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_xor":
        pred = [(a < b) != (c < d) for a, b, c, d in zip(U, V, C, D)]
        return [0x4400 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_selected":
        pred = [(b < c) if (a & 1) else (c == d)
                for a, b, c, d in zip(U, V, C, D)]
        return [0x4500 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_fanout":
        pred = [a < b for a, b in zip(U, V)]
        return [((0x4600 + i) ^ 0xff) if q else (0x4700 + i)
                for i, q in enumerate(pred)]
    if name == "bool_value_only":
        pred = [((a < b) and (c != d)) or ((a ^ d) == 7)
                for a, b, c, d in zip(U, V, C, D)]
        return [(0x4800 if q else 0x4900) + i for i, q in enumerate(pred)]
    if name == "bool_and_direct":
        pred = [(a < b) and (c != d) for a, b, c, d in zip(U, V, C, D)]
        return [0x4a00 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_or_direct":
        pred = [(a < b) or (c == d) for a, b, c, d in zip(U, V, C, D)]
        return [0x4b00 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_arith_nonzero":
        pred = [((((a * 3 + b) & 0xffffffff) ^ c) != 0)
                for a, b, c in zip(U, V, C)]
        return [0x4c00 + i if q else 0 for i, q in enumerate(pred)]
    if name == "bool_fanout_side_effect":
        pred = [a < b for a, b in zip(U, V)]
        return [0x4d00 + i if q else 0 for i, q in enumerate(pred)]
    raise KeyError(name)


def reuse_expected(name):
    if name == "u_lt_reuse_a":
        return [((a + 0x5000) & 0xffffffff) if a < b else 0
                for a, b in zip(U, V)]
    if name == "u_lt_reuse_b":
        return [((b + 0x5100) & 0xffffffff) if a < b else 0
                for a, b in zip(U, V)]
    if name == "u_lt_reuse_both":
        return [((a + b + 0x5200) & 0xffffffff) if a < b else 0
                for a, b in zip(U, V)]
    if name == "u_eq_reuse_both":
        return [((a + b + 0x5300) & 0xffffffff) if a == b else 0
                for a, b in zip(U, V)]
    raise KeyError(name)


def immediate_expected(name):
    specs = {
        "u_lt_imm": (U, lambda x: x < 17, 0x6000),
        "u_ge_imm": (U, lambda x: x >= 17, 0x6100),
        "u_eq_imm": (U, lambda x: x == 17, 0x6200),
        "u_ne_imm": (U, lambda x: x != 17, 0x6300),
        "s_lt_imm": (S, lambda x: x < -7, 0x6400),
        "f_lt_imm": (F, lambda x: x < 0.5, 0x6500),
    }
    values, predicate, marker = specs[name]
    return [marker + i if predicate(value) else 0
            for i, value in enumerate(values)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("predicate_conditions.metal"))
    ap.add_argument("--archives", type=Path, default=Path("archives"))
    ap.add_argument("--workdir", type=Path, default=Path("run"))
    ap.add_argument("--output", type=Path, default=Path("native_results.json"))
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)

    paths = {}
    for index, (values, kind) in enumerate(((U, "u"), (V, "u"),
                                             (C, "u"), (D, "u")), start=1):
        path = args.workdir / f"u{index}.bin"
        path.write_bytes(pack(values, kind))
        paths[index] = path.resolve()
    signed_paths = dict(paths)
    for index, values in ((1, S), (2, T)):
        path = args.workdir / f"s{index}.bin"
        path.write_bytes(pack(values, "s"))
        signed_paths[index] = path.resolve()
    float_paths = dict(paths)
    for index, values in ((1, F), (2, G)):
        path = args.workdir / f"f{index}.bin"
        path.write_bytes(pack(values, "f"))
        float_paths[index] = path.resolve()

    functions = ([f"{kind}_{rel}" for kind in ("u", "s", "f")
                  for rel in RELATIONS] +
                 ["bool_bit_test", "bool_and", "bool_or", "bool_xor",
                  "bool_selected", "bool_fanout", "bool_value_only"] +
                 ["bool_and_direct", "bool_or_direct", "bool_arith_nonzero",
                  "bool_fanout_side_effect"] +
                 ["u_lt_reuse_a", "u_lt_reuse_b", "u_lt_reuse_both",
                  "u_eq_reuse_both"] +
                 ["u_lt_imm", "u_ge_imm", "u_eq_imm", "u_ne_imm",
                  "s_lt_imm", "f_lt_imm"])
    results = {}
    for name in functions:
        selected = signed_paths if name.startswith("s_") else (
            float_paths if name.startswith("f_") else paths)
        got, stdout, stderr = run_one(
            args.agxrun.resolve(), (args.archives / f"{name}.bin").resolve(),
            args.source.resolve(), name, selected, args.workdir.resolve())
        if "reuse" in name:
            expected = reuse_expected(name)
        elif name.endswith("_imm"):
            expected = immediate_expected(name)
        elif name[1:2] == "_":
            expected = direct_expected(name)
        else:
            expected = bool_expected(name)
        match = got == expected
        results[name] = {"status": "MATCH" if match else "MISMATCH",
                         "got": got, "expected": expected,
                         "stdout": stdout, "stderr": stderr}
        print(f"{name:16s} {'MATCH' if match else 'MISMATCH'}")
        if not match:
            print(f"  got      {got}")
            print(f"  expected {expected}")

    args.output.write_text(json.dumps(results, indent=2) + "\n")
    if not all(row["status"] == "MATCH" for row in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
