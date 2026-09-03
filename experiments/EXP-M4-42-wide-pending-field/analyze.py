#!/usr/bin/env python3
"""Gate EXP-M4-42 hardware results and summarize the own-source corpus."""

from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "agx-isa"))
import isadb  # noqa: E402


CONFIRMED_FAMILIES = {
    "iadd2", "imad", "ishift", "ibfe", "ibfins", "ibitcount",
    "cvt_i2f", "cvt_f2i", "fspecial",
}


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pending_mask(raw: bytes) -> int:
    """Instruction bits 12--17, stored across byte 1 and byte 2."""
    return (raw[1] >> 4) | ((raw[2] & 0x03) << 4)


def load_agxparse():
    path = REPO / "tools" / "shdump" / "agxparse.py"
    spec = importlib.util.spec_from_file_location("exp42_agxparse", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def corpus_census() -> dict:
    root = REPO / "experiments" / "EXP-M4-13-full-corpus" / "hex"
    counts: dict[str, Counter] = defaultdict(Counter)
    examples: dict[str, dict[str, dict]] = defaultdict(dict)
    programs = clean = 0
    for path in sorted(root.glob("*.hex")):
        raw_program = bytes.fromhex(path.read_text())
        programs += 1
        offset = 0
        complete = True
        while offset < len(raw_program):
            try:
                record, length = isadb.decode_one(raw_program, offset)
            except Exception:
                complete = False
                break
            if not length:
                complete = False
                break
            raw = raw_program[offset:offset + length]
            mnemonic = record["mnemonic"]
            if (mnemonic in CONFIRMED_FAMILIES and len(raw) >= 3 and
                    (raw[2] & 0xFC) == 0x54):
                mask = pending_mask(raw)
                counts[mnemonic][mask] += 1
                examples[mnemonic].setdefault(f"0x{mask:02x}", {
                    "path": str(path.relative_to(REPO)),
                    "offset": offset,
                    "hex": raw.hex(),
                })
            offset += length
        clean += complete and offset == len(raw_program)

    return {
        "programs": programs,
        "fully_decoded": clean,
        "note": (
            "Decoder-visible census only. The reconciled decoder ignores the "
            "pending-mask high nibble when selecting conversion and bitfield "
            "forms; hardware crosses, not these totals, establish the field geometry."),
        "families": {
            mnemonic: {
                "total": sum(mask_counts.values()),
                "masks": {f"0x{mask:02x}": count
                          for mask, count in sorted(mask_counts.items())},
                "examples": examples[mnemonic],
            }
            for mnemonic, mask_counts in sorted(counts.items())
        },
    }


def main() -> int:
    hardware = json.loads((HERE / "HARDWARE_RESULTS.json").read_text())
    cross = json.loads((HERE / "CROSS_RESULTS.json").read_text())
    mixed = json.loads((HERE / "MIXED_RESULTS.json").read_text())

    matrix_by_function: dict[str, list[dict]] = defaultdict(list)
    for record in hardware["records"]:
        matrix_by_function[record["function"]].append(record)

    required_slot6 = {
        "u2f_load", "i2f_load", "f2u_load", "reciprocal_load",
        "popcount_load", "clz_load", "shift_load", "imad_load",
        "extract_load",
    }
    for function in required_slot6:
        records = matrix_by_function[function]
        for record in records:
            expected = bool(record["mask"] & 0x20)
            if record["exact"] != expected:
                raise RuntimeError(
                    f"{function}: mask {record['mask']:#x} exact="
                    f"{record['exact']}, expected {expected}")

    load_cross = [r for r in cross["records"]
                  if r["kind"] == "device_load_cross"]
    get_sr_cross = [r for r in cross["records"]
                    if r["kind"] == "get_sr_cross"]
    for record in load_cross:
        expected = record["relation"] != "neighbor"
        if record["exact"] != expected:
            raise RuntimeError(f"load cross mismatch: {record}")
    if not get_sr_cross or not all(r["exact"] for r in get_sr_cross):
        raise RuntimeError("GET_SR cross is not uniformly exact")

    mixed_zero = [r for r in mixed["records"] if r["relation"] == "zero"]
    mixed_both = [r for r in mixed["records"] if r["relation"] == "both"]
    mixed_single = [r for r in mixed["records"]
                    if r["relation"] in ("first", "second")]
    if any(r["exact"] for r in mixed_zero):
        raise RuntimeError("zero-mask mixed-source case unexpectedly exact")
    if not all(r["exact"] for r in mixed_both):
        raise RuntimeError("a composite-mask mixed-source case failed")
    if not any(not r["exact"] for r in mixed_single):
        raise RuntimeError("mixed test lacks a sensitivity-positive one-bit arm")

    # One native function walks all six slots.  These offsets are instruction
    # boundaries established by its exact own-source decode.
    absmulti_path = (REPO / "experiments" / "EXP-M4-13-full-corpus" /
                     "hex" / "dec_iso_absmulti.hex")
    absmulti = bytes.fromhex(absmulti_path.read_text())
    absmulti_offsets = (0xDE, 0xE8, 0x116, 0x134, 0x162, 0x180)
    absmulti_masks = [pending_mask(absmulti[offset:offset + 10])
                      for offset in absmulti_offsets]
    if absmulti_masks != [0x20, 0x01, 0x02, 0x04, 0x08, 0x10]:
        raise RuntimeError(f"six-slot native walk drift: {absmulti_masks}")

    # GET_SR's suffix walks 0x06/0x26/0x46 in a native three-system-value
    # shader, while its two direct conversions carry mask bits 0 and 1.
    agxparse = load_agxparse()
    sys_three_path = HERE / "raw" / "native" / "sys_three.archive.bin"
    _report, stages = agxparse.extract_all_stages(sys_three_path.read_bytes())
    sys_three = stages["compute"]["_agc.main"]
    get_sr_suffixes = [sys_three[offset + 3] for offset in (0x00, 0x04, 0x08)]
    conversion_masks = [pending_mask(sys_three[offset:offset + 8])
                        for offset in (0x0C, 0x14)]
    if get_sr_suffixes != [0x06, 0x26, 0x46]:
        raise RuntimeError(f"GET_SR suffix walk drift: {get_sr_suffixes}")
    if conversion_masks != [0x01, 0x02]:
        raise RuntimeError(f"GET_SR consumer-mask drift: {conversion_masks}")

    output = {
        "schema_version": 1,
        "field": {
            "instruction_bits": [12, 17],
            "slot_to_mask": {str(slot): 1 << (slot - 1)
                             for slot in range(1, 7)},
            "encoding": {
                "slots_1_to_4": "byte1 bits 4..7",
                "slots_5_to_6": "byte2 bits 0..1",
            },
        },
        "hardware": {
            "single_slot_matrix_records": len(hardware["records"]),
            "device_load_cross_records": len(load_cross),
            "device_load_cross_exact": sum(r["exact"] for r in load_cross),
            "get_sr_cross_records": len(get_sr_cross),
            "get_sr_cross_exact": sum(r["exact"] for r in get_sr_cross),
            "mixed_slot_records": len(mixed["records"]),
            "mixed_both_exact": sum(r["exact"] for r in mixed_both),
            "mixed_single_nonexact": sum(not r["exact"] for r in mixed_single),
        },
        "native_witnesses": {
            "six_slot_iadd_walk": {
                "path": str(absmulti_path.relative_to(REPO)),
                "offsets": list(absmulti_offsets),
                "masks": absmulti_masks,
            },
            "get_sr_three_value_walk": {
                "path": str(sys_three_path.relative_to(REPO)),
                "suffixes": get_sr_suffixes,
                "conversion_masks": conversion_masks,
            },
        },
        "corpus": corpus_census(),
        "artifacts": {
            path.name: sha256(path)
            for path in (HERE / "HARDWARE_RESULTS.json",
                         HERE / "CROSS_RESULTS.json",
                         HERE / "MIXED_RESULTS.json",
                         HERE / "kernels" / "consumers.metal")
        },
    }
    (HERE / "ANALYSIS.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print("EXP_M4_42_OK "
          f"single={len(hardware['records'])} "
          f"load_cross={len(load_cross)} "
          f"get_sr_cross={len(get_sr_cross)} "
          f"mixed={len(mixed['records'])} "
          f"corpus={output['corpus']['programs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
