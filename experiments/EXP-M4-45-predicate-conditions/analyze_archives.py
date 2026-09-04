#!/usr/bin/env python3
"""Extract and classify instructions from the experiment's own archives."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archives", type=Path, default=Path("raw/archives"))
    ap.add_argument("--agxparse", type=Path, required=True)
    ap.add_argument("--isa-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("raw/native_analysis.json"))
    args = ap.parse_args()

    agxparse = load_module("agxparse", args.agxparse)
    sys.path.insert(0, str(args.isa_dir))
    import isadb

    result = {}
    for archive in sorted(args.archives.glob("*.bin")):
        raw = archive.read_bytes()
        _, pieces = agxparse.extract_agx(raw)
        main = pieces["_agc.main"]
        recs, leftover = isadb.disassemble(main)
        offset = 0
        instructions = []
        predicates = []
        for rec in recs:
            encoded_len = len(bytes.fromhex(rec["hex"]))
            row = {
                "offset": offset,
                "length": rec.get("length") or encoded_len,
                "mnemonic": rec.get("mnemonic"),
                "op_mnemonic": rec.get("op_mnemonic"),
                "hex": rec["hex"],
                "fields": rec.get("fields", {}),
            }
            instructions.append(row)
            if row["mnemonic"] == "icmp_pred":
                predicates.append(row)
            offset += row["length"]
        # The checked-in DB intentionally still carries the earlier six-byte
        # hypothesis.  Decode the focused predicate family independently so
        # the experiment can expose (rather than hide) the newly observed
        # ten-byte form selected by byte-2 bit 0.
        focused = []
        for off in range(len(main) - 5):
            if (main[off] & 0x0f) != 0x0a:
                continue
            if (main[off] >> 4) not in (0, 1):
                continue
            extended = bool(main[off + 2] & 1)
            if extended:
                if off + 10 > len(main) or main[off + 4:off + 6] != b"\x06\x00":
                    continue
                length = 10
                condition = main[off + 6]
                if (condition & ~0x10) not in range(8):
                    continue
            else:
                if (main[off + 4] & ~0x10) not in range(8):
                    continue
                length = 6
                condition = main[off + 4]
            focused.append({
                "offset": off,
                "length": length,
                "hex": main[off:off + length].hex(),
                "byte0_high": main[off] >> 4,
                "srcA_desc": main[off + 1] & 0x7f,
                "srcA_bit7": bool(main[off + 1] & 0x80),
                "control": main[off + 2],
                "release_A": bool(main[off + 2] & 0x08),
                "release_B": bool(main[off + 2] & 0x10),
                "extended": extended,
                "srcB_desc": main[off + 3] & 0x7f,
                "srcB_bit7": bool(main[off + 3] & 0x80),
                "condition": condition,
            })

        result[archive.stem] = {
            "archive": str(archive),
            "main_length": len(main),
            "main_hex": main.hex(),
            "leftover_hex": leftover.hex(),
            "instructions": instructions,
            "predicate_compares": predicates,
            "focused_predicate_candidates": focused,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")

    for name, row in result.items():
        preds = row["predicate_compares"]
        print(f"{name:16s} len={row['main_length']:3d} "
              f"preds={len(preds)} leftover={len(bytes.fromhex(row['leftover_hex']))}")
        for pred in preds:
            print(f"  +0x{pred['offset']:02x} {pred['hex']} {pred['fields']}")
        for pred in row["focused_predicate_candidates"]:
            print(f"    focused +0x{pred['offset']:02x}/{pred['length']} "
                  f"{pred['hex']} inv={pred['byte0_high']} "
                  f"relA={int(pred['release_A'])} relB={int(pred['release_B'])} "
                  f"cond={pred['condition']:#x}")


if __name__ == "__main__":
    main()
