#!/usr/bin/env python3
"""Hardware ablations for localized predicate and mask-control fields."""

import argparse
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

from run_native import U, V, S, T, F, G, pack


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def marked(predicate, marker):
    return [marker + i if q else 0 for i, q in enumerate(predicate)]


def bitwise_float_eq(a, b):
    return [struct.pack("<f", x) == struct.pack("<f", y) for x, y in zip(a, b)]


def invoke(agxrun, archive, source, function, paths, workdir):
    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--grid", "16", "--tg", "16"]
    for index, path in sorted(paths.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", "0=64"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25,
                              cwd=workdir)
    except subprocess.TimeoutExpired:
        return {"status": "HANG"}
    status = None
    output = None
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS "):
            status = line.split(None, 1)[1]
        elif line.startswith("OUT 0 "):
            output = list(struct.unpack("<16I", bytes.fromhex(line.split(None, 2)[2])))
    return {"status": status or f"EXIT_{proc.returncode}", "output": output,
            "stdout": proc.stdout, "stderr": proc.stderr}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--agxparse", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("predicate_conditions.metal"))
    ap.add_argument("--archives", type=Path, default=Path("archives"))
    ap.add_argument("--workdir", type=Path, default=Path("ablations"))
    ap.add_argument("--output", type=Path, default=Path("ablation_results.json"))
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    agxparse = load_module("agxparse", args.agxparse.resolve())

    data = {}
    for label, lhs, rhs, kind in (("u", U, V, "u"), ("s", S, T, "s"),
                                  ("f", F, G, "f")):
        paths = {}
        for index, values in ((1, lhs), (2, rhs)):
            path = (args.workdir / f"{label}{index}.bin").resolve()
            path.write_bytes(pack(values, kind))
            paths[index] = path
        data[label] = paths

    tests = [
        # The short ordered form: condition code and both operand high bits.
        ("u_lt_control", "u_lt", "u", {}, marked([a < b for a, b in zip(U, V)], 0x1000)),
        ("u_lt_cond_to_u_gt", "u_lt", "u", {0x24: 0x04}, marked([a > b for a, b in zip(U, V)], 0x1000)),
        ("u_lt_cond_to_s_lt", "u_lt", "s", {0x24: 0x07}, marked([a < b for a, b in zip(S, T)], 0x1000)),
        ("u_lt_cond_to_f_lt", "u_lt", "f", {0x24: 0x03}, marked([a < b for a, b in zip(F, G)], 0x1000)),
        ("u_lt_push_invert", "u_lt", "u", {0x29: 0x21}, marked([a >= b for a, b in zip(U, V)], 0x1000)),
        ("u_lt_retain_srcA", "u_lt", "u", {0x21: 0x83}, marked([a < b for a, b in zip(U, V)], 0x1000)),
        ("u_lt_retain_srcB", "u_lt", "u", {0x23: 0x85}, marked([a < b for a, b in zip(U, V)], 0x1000)),
        ("u_lt_byte0_hi", "u_lt", "u", {0x20: 0x1a},
         marked([not (a < b) for a, b in zip(U, V)], 0x1000)),

        # Native liveness forms: isolate the duplicated-looking descriptor and
        # byte-2 controls while the compared value is genuinely read later.
        ("reuse_a_control", "u_lt_reuse_a", "u", {},
         [((a + 0x5000) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_a_clear_src_hi", "u_lt_reuse_a", "u", {0x21: 0x03},
         [((a + 0x5000) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_a_set_byte2_release", "u_lt_reuse_a", "u", {0x22: 0x3a},
         [0x5000 if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_a_clear_both", "u_lt_reuse_a", "u", {0x21: 0x03, 0x22: 0x3a},
         [0x5000 if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_b_control", "u_lt_reuse_b", "u", {},
         [((b + 0x5100) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_b_clear_src_hi", "u_lt_reuse_b", "u", {0x23: 0x03},
         [((b + 0x5100) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_b_set_byte2_release", "u_lt_reuse_b", "u", {0x22: 0x3a},
         [0x5100 if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_b_clear_both", "u_lt_reuse_b", "u", {0x23: 0x03, 0x22: 0x3a},
         [0x5100 if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_both_control", "u_lt_reuse_both", "u", {},
         [((a + b + 0x5200) & 0xffffffff) if a < b else 0
          for a, b in zip(U, V)]),
        ("reuse_both_release_A", "u_lt_reuse_both", "u", {0x22: 0x2a},
         [((b + 0x5200) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_both_release_B", "u_lt_reuse_both", "u", {0x22: 0x32},
         [((a + 0x5200) & 0xffffffff) if a < b else 0 for a, b in zip(U, V)]),
        ("reuse_both_release_both", "u_lt_reuse_both", "u", {0x22: 0x3a},
         [0x5200 if a < b else 0 for a, b in zip(U, V)]),

        # Equality has an additional four-byte companion/form extension.
        ("u_eq_control", "u_eq", "u", {}, marked([a == b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_push_invert", "u_eq", "u", {0x2d: 0x21}, marked([a != b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_byte0_hi", "u_eq", "u", {0x20: 0x1a}, marked([a != b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_double_invert", "u_eq", "u", {0x20: 0x1a, 0x2d: 0x21}, marked([a == b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_on_float_bits", "u_eq", "f", {}, marked(bitwise_float_eq(F, G), 0x1000)),
        ("u_eq_companion_to_float", "u_eq", "f", {0x26: 0x00}, marked([a == b for a, b in zip(F, G)], 0x1000)),
        ("u_eq_retain_srcA", "u_eq", "u", {0x21: 0x83}, marked([a == b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_retain_srcB", "u_eq", "u", {0x23: 0x85}, marked([a == b for a, b in zip(U, V)], 0x1000)),
        ("u_eq_reuse_control", "u_eq_reuse_both", "u", {},
         [((a + b + 0x5300) & 0xffffffff) if a == b else 0
          for a, b in zip(U, V)]),
        ("u_eq_reuse_clear_src_hi", "u_eq_reuse_both", "u", {0x21: 0x03},
         [((a + b + 0x5300) & 0xffffffff) if a == b else 0
          for a, b in zip(U, V)]),
        ("u_eq_reuse_release_A", "u_eq_reuse_both", "u", {0x22: 0x3b},
         [0x5300 if a == b else 0 for a, b in zip(U, V)]),

        # Float <=/>= differ in exactly byte +6 of their native 10-byte form.
        ("f_ge_control", "f_ge", "f", {}, marked([a >= b for a, b in zip(F, G)], 0x3000)),
        ("f_ge_companion_to_le", "f_ge", "f", {0x26: 0x03}, marked([a <= b for a, b in zip(F, G)], 0x3000)),
        ("f_ge_byte0_hi_clear", "f_ge", "f", {0x20: 0x0a},
         marked([not (a >= b) for a, b in zip(F, G)], 0x3000)),
        ("f_eq_companion_to_integer", "f_eq", "f", {0x26: 0x07}, marked(bitwise_float_eq(F, G), 0x3000)),
    ]

    results = {}
    hangs = 0
    for name, carrier, kind, changes, expected in tests:
        archive_raw = (args.archives / f"{carrier}.bin").read_bytes()
        base, length = agxparse.locate_region(archive_raw, "_agc.main")
        mutated = bytearray(archive_raw)
        notes = []
        for offset, value in changes.items():
            if offset >= length:
                raise ValueError(f"{name}: offset {offset:#x} outside main")
            old = mutated[base + offset]
            mutated[base + offset] = value
            notes.append({"main_offset": offset, "old": old, "new": value})
        archive = (args.workdir / f"{name}.bin").resolve()
        archive.write_bytes(mutated)
        row = invoke(args.agxrun.resolve(), archive, args.source.resolve(), carrier,
                     data[kind], args.workdir.resolve())
        row["carrier"] = carrier
        row["input_kind"] = kind
        row["splices"] = notes
        row["expected"] = expected
        if row["status"] == "HANG":
            hangs += 1
        if expected is not None and row.get("output") is not None:
            row["verdict"] = "MATCH" if row["output"] == expected else "MISMATCH"
        else:
            row["verdict"] = "OBSERVE"
        results[name] = row
        print(f"{name:28s} {row['status']:12s} {row['verdict']}")
        if row["verdict"] in ("MISMATCH", "OBSERVE") and row.get("output") is not None:
            print(f"  output {row['output']}")
        if hangs >= 2:
            print("Stopping after two hangs")
            break

    args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
