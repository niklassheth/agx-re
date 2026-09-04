#!/usr/bin/env python3
"""Hardware cross for Apple9 predicate producers and mask consumers."""

import argparse
import importlib.util
import json
from pathlib import Path
import struct
import subprocess


U = [0, 1, 5, 0xffffffff, 0x80000000, 7, 42, 9,
     16, 15, 31, 32, 0x7fffffff, 2, 100, 3]
V = [1, 0, 5, 0, 0xffffffff, 7, 41, 10,
     15, 16, 32, 31, 0x80000000, 3, 2, 100]
COUNT = [0, 1, 2, 3, 4, 5, 7, 8, 11, 13, 16, 19, 23, 29, 31, 37]
AUX = [0x01020304, 0x11223344, 0xdeadbeef, 0, 1, 7, 19, 0xffffffff,
       0x80000000, 0x7fffffff, 0x13579bdf, 0x2468ace0, 3, 5, 11, 17]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pack_u32(values):
    return b"".join(struct.pack("<I", value) for value in values)


def locate_unique(blob, needle, label):
    offsets = []
    start = 0
    while True:
        offset = blob.find(needle, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    if len(offsets) != 1:
        raise RuntimeError(f"expected one {label}, found {offsets}")
    return offsets[0]


def invoke(agxrun, archive, source, function, inputs, out_size, workdir,
           no_fast_math=False):
    cmd = [str(agxrun), "--archive", str(archive), "--source", str(source),
           "--function", function, "--grid", "16", "--tg", "16"]
    if no_fast_math:
        cmd.append("--no-fast-math")
    for index, path in sorted(inputs.items()):
        cmd += ["--buf", f"{index}={path}"]
    cmd += ["--out", f"0={out_size}"]
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
        result["words"] = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    return result


def predicate_expected(invert=False):
    return [0x1000 + lane if ((a < b) != invert) else 0
            for lane, (a, b) in enumerate(zip(U, V))]


def loop_expected():
    words = []
    for lane, (count, aux) in enumerate(zip(COUNT, AUX)):
        value = aux ^ 0xb0c0d0e0
        for i in range(count):
            value = (value * 3 + 7) & 0xffffffff
            value ^= i + 0x123
        words += [value & 0xffffffff, count, count, 0xb0000000 | lane]
    return words


def verdict(row, expected):
    if row["status"] == "HANG":
        return "HANG"
    return "MATCH" if row.get("words") == expected else "MISMATCH"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agxrun", type=Path, required=True)
    parser.add_argument("--agxparse", type=Path, required=True)
    parser.add_argument("--predicate-source", type=Path, required=True)
    parser.add_argument("--predicate-archive", type=Path, required=True)
    parser.add_argument("--loop-source", type=Path, required=True)
    parser.add_argument("--loop-archive", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, default=Path("work"))
    parser.add_argument("--output", type=Path,
                        default=Path("raw/ablation_results.json"))
    args = parser.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    agxparse = load_module("agxparse", args.agxparse.resolve())

    u_path = (args.workdir / "u.bin").resolve()
    v_path = (args.workdir / "v.bin").resolve()
    u_path.write_bytes(pack_u32(U))
    v_path.write_bytes(pack_u32(V))
    predicate_inputs = {1: u_path, 2: v_path}

    predicate_raw = args.predicate_archive.read_bytes()
    predicate_base, predicate_length = agxparse.locate_region(
        predicate_raw, "_agc.main", stage="compute")
    predicate_main = predicate_raw[predicate_base:
                                   predicate_base + predicate_length]
    compare_offset = locate_unique(predicate_main, bytes.fromhex("0a033a0505c0"),
                                   "u_lt predicate comparison")
    push_offset = locate_unique(predicate_main, bytes.fromhex("0f055401"),
                                "u_lt execution-mask push")

    results = {"predicate_push_cross": {}, "loop_update_cross": {}}

    def run_predicate(name, bank, selected_bank, invert=False,
                      expected_override=None):
        changed = bytearray(predicate_raw)
        changed[predicate_base + compare_offset] = 0x0a | (bank << 5)
        changed[predicate_base + push_offset + 3] = (
            1 + 4 * selected_bank + (0x20 if invert else 0))
        archive = (args.workdir / f"{name}.bin").resolve()
        archive.write_bytes(changed)
        row = invoke(args.agxrun.resolve(), archive,
                     args.predicate_source.resolve(), "u_lt", predicate_inputs,
                     64, args.workdir.resolve())
        expected = (predicate_expected(invert) if expected_override is None
                    else expected_override)
        row.update({"compare_bank": bank, "push_bank": selected_bank,
                    "push_invert": invert, "expected": expected,
                    "verdict": verdict(row, expected)})
        results["predicate_push_cross"][name] = row
        print(f"{name:28s} {row['status']:12s} {row['verdict']}")
        return row

    # Establish all eight syntactically encodable bank pairs.
    for bank in range(8):
        run_predicate(f"diagonal_bank_{bank}", bank, bank)

    # Crossed controls distinguish addressing from ignored fields/aliases.
    for bank, selected in ((1, 0), (0, 1), (2, 1), (1, 2), (7, 0), (0, 7)):
        run_predicate(f"offdiag_write_{bank}_read_{selected}", bank, selected)

    # Inversion must remain orthogonal to the selected bank.
    for bank in (0, 1, 4, 7):
        run_predicate(f"inverted_bank_{bank}", bank, bank, True)

    # Selector sources six and seven are outside the six diagonal pairs above.
    # Test them with an otherwise ordinary bank-zero comparison so any constant
    # behavior cannot be attributed to the compare's destination encoding.
    all_true = [0x1000 + lane for lane in range(16)]
    all_false = [0] * 16
    run_predicate("selector_6", 0, 6, expected_override=all_true)
    run_predicate("selector_6_inverted", 0, 6, True,
                  expected_override=all_false)
    run_predicate("selector_7", 0, 7, expected_override=all_false)
    run_predicate("selector_7_inverted", 0, 7, True,
                  expected_override=all_true)

    # Recheck the unmodified path after the mutation group.
    run_predicate("final_predicate_control", 0, 0)

    count_path = (args.workdir / "count.bin").resolve()
    aux_path = (args.workdir / "aux.bin").resolve()
    count_path.write_bytes(pack_u32(COUNT))
    aux_path.write_bytes(pack_u32(AUX))
    loop_inputs = {1: count_path, 2: aux_path}
    loop_raw = args.loop_archive.read_bytes()
    loop_base, loop_length = agxparse.locate_region(
        loop_raw, "_agc.main", stage="compute")
    loop_main = loop_raw[loop_base:loop_base + loop_length]
    latch_compare = locate_unique(loop_main, bytes.fromhex("0a0523830600"),
                                  "pc_base_probe latch comparison")
    latch_update = locate_unique(loop_main, bytes.fromhex("8f045422"),
                                 "pc_base_probe loop update")
    loop_want = loop_expected()

    def run_loop(name, compare_bank, update_bank, compare_invert=False,
                 update_invert=True):
        changed = bytearray(loop_raw)
        changed[loop_base + latch_compare] = (
            0x0a | (compare_bank << 5) | (0x10 if compare_invert else 0))
        changed[loop_base + latch_update + 3] = (
            0x02 | (update_bank << 2) | (0x20 if update_invert else 0))
        archive = (args.workdir / f"{name}.bin").resolve()
        archive.write_bytes(changed)
        row = invoke(args.agxrun.resolve(), archive, args.loop_source.resolve(),
                     "pc_base_probe", loop_inputs, 256,
                     args.workdir.resolve(), no_fast_math=True)
        row.update({"compare_bank": compare_bank, "update_bank": update_bank,
                    "compare_invert": compare_invert,
                    "update_invert": update_invert,
                    "expected": loop_want,
                    "verdict": verdict(row, loop_want)})
        results["loop_update_cross"][name] = row
        print(f"{name:28s} {row['status']:12s} {row['verdict']}")
        return row

    for name, write_bank, read_bank, compare_invert, update_invert in (
            ("loop_native_0_0", 0, 0, False, True),
            ("loop_diagonal_1_1", 1, 1, False, True),
            ("loop_diagonal_2_2", 2, 2, False, True),
            ("loop_double_invert", 0, 0, True, False),
            ("loop_update_invert_only", 0, 0, False, False),
            ("loop_write_1_read_0", 1, 0, False, True),
            ("loop_write_0_read_1", 0, 1, False, True)):
        row = run_loop(name, write_bank, read_bank, compare_invert,
                       update_invert)
        if row["status"] == "HANG":
            break

    args.output.write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
