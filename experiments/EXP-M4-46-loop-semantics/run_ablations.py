#!/usr/bin/env python3
"""Focused hardware ablations for Apple9 loop control.

The carrier is our own ``pc_base_probe`` MSL kernel.  Its single backward
``jump`` is redirected to the native loop-pop instruction.  This is a useful
base-address discriminator because:

* ``jump_start + patched_displacement`` is the start of the loop pop; and
* ``jump_start + 4 + patched_displacement`` is four bytes into that instruction.

The start-relative interpretation therefore produces a well-defined one-trip
loop without depending on a GPU fault as the signal.

The same harness also changes the latch's mask selector in both directions and
toggles its 0x54/0x56 form bit.  The compound 0x02 -> 0x22 arm is allowed one
watchdog hang and is not repeated.
"""

import argparse
import importlib.util
import json
from pathlib import Path

from run_native import AUX, COUNT, CUT, execute, expected


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_unique(blob, needle, label):
    found = []
    start = 0
    while True:
        offset = blob.find(needle, start)
        if offset < 0:
            break
        found.append(offset)
        start = offset + 1
    if len(found) != 1:
        raise RuntimeError(f"expected one {label}, found {found}")
    return found[0]


def one_trip_expected(lane):
    n = COUNT[lane]
    value = AUX[lane] ^ 0xB0C0D0E0
    iterations = 0
    if n:
        value = ((value * 3 + 7) & 0xFFFFFFFF) ^ 0x123
        iterations = 1
    # Metal proves the loop induction value equals the original trip count and
    # uses that value directly after the loop.  Retargeting the machine-code
    # backedge changes the carried recurrence, but not this optimized output.
    return value & 0xFFFFFFFF, n, n, 0xB0000000 | lane


def flattened(oracle):
    return [word for lane in range(16) for word in oracle(lane)]


def verdict(row, want):
    return "MATCH" if row.get("words") == want else "MISMATCH"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agxrun", type=Path, required=True)
    ap.add_argument("--agxparse", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=Path("loop_semantics.metal"))
    ap.add_argument("--archive", type=Path,
                    default=Path("work/native/archives/pc_base_probe.bin"))
    ap.add_argument("--workdir", type=Path, default=Path("work/ablations"))
    ap.add_argument("--output", type=Path,
                    default=Path("raw/ablation_results.json"))
    args = ap.parse_args()
    args.workdir.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)

    agxparse = load_module("agxparse", args.agxparse.resolve())
    archive_raw = args.archive.read_bytes()
    main_base, main_length = agxparse.locate_region(
        archive_raw, "_agc.main", stage="compute")
    main_bytes = archive_raw[main_base:main_base + main_length]

    jump_offset = find_unique(main_bytes, bytes.fromhex("0f0054"), "jump")
    pop_offset = find_unique(main_bytes, bytes.fromhex("0f0604020000"),
                             "loop pop")
    native_delta = int.from_bytes(main_bytes[jump_offset + 3:jump_offset + 9],
                                  "little", signed=True)
    patched_delta = pop_offset - jump_offset
    if native_delta >= 0 or patched_delta <= 0:
        raise RuntimeError((native_delta, patched_delta))

    mutated = bytearray(archive_raw)
    mutated[main_base + jump_offset + 3:main_base + jump_offset + 9] = \
        patched_delta.to_bytes(6, "little", signed=True)
    patched_archive = (args.workdir / "pc_base_to_loop_pop.bin").resolve()
    patched_archive.write_bytes(mutated)

    inputs = {
        1: (args.workdir / "input1.bin").resolve(),
        2: (args.workdir / "input2.bin").resolve(),
    }
    from run_native import pack_u32
    inputs[1].write_bytes(pack_u32(COUNT))
    inputs[2].write_bytes(pack_u32(AUX))

    control = execute(args.agxrun.resolve(), args.source.resolve(),
                      "pc_base_probe", args.archive.resolve(), inputs,
                      args.workdir.resolve())
    control_want = flattened(lambda lane: expected("pc_base_probe", lane))
    control["expected"] = control_want
    control["verdict"] = verdict(control, control_want)

    retarget = execute(args.agxrun.resolve(), args.source.resolve(),
                       "pc_base_probe", patched_archive, inputs,
                       args.workdir.resolve())
    retarget_want = flattened(one_trip_expected)
    retarget["expected"] = retarget_want
    retarget["verdict"] = verdict(retarget, retarget_want)

    # The broad corpus contains outer-depth updates ending in both 0x02 and
    # 0x22, so bit 0x20 cannot itself be the mask depth.  Change only that bit
    # in the exact pc_base_probe to test whether the two forms preserve the
    # same basic loop semantics.
    latch_offset = find_unique(main_bytes, bytes.fromhex("8f045422"),
                               "outer loop mask update")
    no_bit20 = bytearray(archive_raw)
    no_bit20[main_base + latch_offset + 3] = 0x02
    no_bit20_archive = (args.workdir / "pc_base_latch_02.bin").resolve()
    no_bit20_archive.write_bytes(no_bit20)
    latch_02 = execute(args.agxrun.resolve(), args.source.resolve(),
                       "pc_base_probe", no_bit20_archive, inputs,
                       args.workdir.resolve())
    latch_02["expected"] = control_want
    latch_02["verdict"] = verdict(latch_02, control_want)

    # Likewise, 0x54 and 0x56 occur in the same 8f 04 family.  Toggle only
    # byte+2 on this uncomplicated latch; this tests semantic compatibility,
    # not the scheduler/lifetime reason Metal chooses one form over the other.
    form56 = bytearray(archive_raw)
    form56[main_base + latch_offset + 2] = 0x56
    form56_archive = (args.workdir / "pc_base_latch_form56.bin").resolve()
    form56_archive.write_bytes(form56)
    latch_form56 = execute(args.agxrun.resolve(), args.source.resolve(),
                           "pc_base_probe", form56_archive, inputs,
                           args.workdir.resolve())
    latch_form56["expected"] = control_want
    latch_form56["verdict"] = verdict(latch_form56, control_want)

    # compound_latch is a fresh exact-output native case where Metal chooses
    # 0x02 for the same outer mask depth.  Test the reverse 0x02 -> 0x22 swap
    # so this distinction is not inferred from only one mutation direction.
    compound_archive_path = args.archive.parent / "compound_latch.bin"
    compound_raw = compound_archive_path.read_bytes()
    compound_base, compound_length = agxparse.locate_region(
        compound_raw, "_agc.main", stage="compute")
    compound_main = compound_raw[compound_base:compound_base + compound_length]
    compound_latch_offset = find_unique(
        compound_main, bytes.fromhex("8f045402"),
        "compound-condition outer loop mask update")
    compound_22_raw = bytearray(compound_raw)
    compound_22_raw[compound_base + compound_latch_offset + 3] = 0x22
    compound_22_archive = (
        args.workdir / "compound_latch_tail_22.bin").resolve()
    compound_22_archive.write_bytes(compound_22_raw)
    compound_inputs = {1: inputs[1], 2: inputs[2]}
    compound_control = execute(
        args.agxrun.resolve(), args.source.resolve(), "compound_latch",
        compound_archive_path.resolve(), compound_inputs,
        args.workdir.resolve())
    compound_want = flattened(lambda lane: expected("compound_latch", lane))
    compound_control["expected"] = compound_want
    compound_control["verdict"] = verdict(compound_control, compound_want)
    compound_22 = execute(
        args.agxrun.resolve(), args.source.resolve(), "compound_latch",
        compound_22_archive, compound_inputs, args.workdir.resolve())
    compound_22["verdict"] = (
        "CHANGED" if compound_22.get("status") == "OK" and
        compound_22.get("words") != compound_control.get("words")
        else "NO_CHANGE")

    # In loop_break, native Metal emits two distinct loop-mask updates, 0x26
    # at the source break and 0x22 at the natural latch.  Mutating the former
    # to the latter is a sensitivity test.  Its result is intentionally treated
    # as an observed compound behavior, not proof that the tail directly names
    # a predicate register.
    break_archive_path = args.archive.parent / "loop_break.bin"
    break_raw = break_archive_path.read_bytes()
    break_base, break_length = agxparse.locate_region(
        break_raw, "_agc.main", stage="compute")
    break_main = break_raw[break_base:break_base + break_length]
    break_update = find_unique(break_main, bytes.fromhex("8f045426"),
                               "break predicate update")
    latch_update = find_unique(break_main, bytes.fromhex("8f045422"),
                               "natural latch update")
    break_mutated = bytearray(break_raw)
    break_mutated[break_base + break_update + 3] = 0x22
    tail_22_archive = (args.workdir / "loop_break_tail_22.bin").resolve()
    tail_22_archive.write_bytes(break_mutated)

    break_inputs = {
        1: inputs[1],
        2: (args.workdir / "cut.bin").resolve(),
    }
    break_inputs[2].write_bytes(pack_u32(CUT))
    break_control = execute(args.agxrun.resolve(), args.source.resolve(),
                            "loop_break", break_archive_path.resolve(),
                            break_inputs, args.workdir.resolve())
    break_want = flattened(lambda lane: expected("loop_break", lane))
    break_control["expected"] = break_want
    break_control["verdict"] = verdict(break_control, break_want)

    tail_22 = execute(args.agxrun.resolve(), args.source.resolve(),
                      "loop_break", tail_22_archive, break_inputs,
                      args.workdir.resolve())
    tail_22["verdict"] = (
        "CHANGED" if tail_22.get("status") == "OK" and
        tail_22.get("words") != break_control.get("words") else "NO_CHANGE")

    result = {
        "carrier": "pc_base_probe",
        "main_length": main_length,
        "jump_offset": jump_offset,
        "loop_pop_offset": pop_offset,
        "native_displacement": native_delta,
        "native_target_from_start": jump_offset + native_delta,
        "native_target_from_plus4": jump_offset + 4 + native_delta,
        "patched_displacement": patched_delta,
        "patched_target_from_start": jump_offset + patched_delta,
        "patched_target_from_plus4": jump_offset + 4 + patched_delta,
        "control": control,
        "retarget_to_loop_pop": retarget,
        "loop_update_orthogonal_bits": {
            "latch_offset": latch_offset,
            "tail_22_to_02": latch_02,
            "form_54_to_56": latch_form56,
            "compound_latch_offset": compound_latch_offset,
            "compound_control": compound_control,
            "compound_tail_02_to_22": compound_22,
        },
        "loop_break_selector": {
            "break_update_offset": break_update,
            "latch_update_offset": latch_update,
            "splice": {
                "offset": break_update + 3,
                "old": 0x26,
                "new": 0x22,
            },
            "control": break_control,
            "tail_26_to_22": tail_22,
        },
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for name, row in (("control", control), ("retarget_to_loop_pop", retarget),
                      ("latch_tail_22_to_02", latch_02),
                      ("latch_form_54_to_56", latch_form56),
                      ("compound_control", compound_control),
                      ("compound_tail_02_to_22", compound_22)):
        print(f"{name:24s} {row['status']:14s} {row['verdict']}")
    for name, row in (("break_control", break_control),
                      ("break_tail_26_to_22", tail_22)):
        print(f"{name:24s} {row['status']:14s} {row['verdict']}")
    print(f"native:  {jump_offset:#x} + ({native_delta}) = "
          f"{jump_offset + native_delta:#x}")
    print(f"patched: {jump_offset:#x} + ({patched_delta}) = "
          f"{jump_offset + patched_delta:#x}")
    if any(row["verdict"] != "MATCH" for row in
           (control, retarget, latch_form56, compound_control,
            break_control)) or \
       latch_02["verdict"] != "MISMATCH" or \
       compound_22.get("status") != "HANG" or \
       tail_22["verdict"] != "CHANGED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
