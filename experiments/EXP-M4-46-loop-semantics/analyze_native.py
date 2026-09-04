#!/usr/bin/env python3
"""Extract native mains and describe Apple9 control-flow instruction topology."""

import argparse
import importlib.util
import json
from pathlib import Path
import sys


CF = {"jump", "jump_cond", "if_push", "pop_reconverge", "mask_op",
      "loop_mask_update", "loop_mask_update_form56", "break_mask_unwind",
      "ret"}


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def signed48(value):
    return value - (1 << 48) if value & (1 << 47) else value


def decode(main, isadb):
    recs, leftover = isadb.disassemble(main)
    rows, boundaries, offset = [], set(), 0
    for rec in recs:
        encoded = bytes.fromhex(rec["hex"])
        length = len(encoded)
        boundaries.add(offset)
        mnemonic = rec.get("op_mnemonic") or rec.get("mnemonic")
        rows.append({
            "offset": offset,
            "length": length,
            "mnemonic": mnemonic,
            "hex": rec["hex"],
            "fields": rec.get("fields", {}),
        })
        offset += length
    boundaries.add(offset)
    for row in rows:
        if row["mnemonic"] not in ("jump", "jump_cond"):
            continue
        delta = signed48(row["fields"]["offset"])
        candidates = {
            "from_start": row["offset"] + delta,
            "from_plus4": row["offset"] + 4 + delta,
            "from_end": row["offset"] + row["length"] + delta,
        }
        row["signed_displacement"] = delta
        row["target_candidates"] = candidates
        row["candidate_is_boundary"] = {
            key: value in boundaries for key, value in candidates.items()
        }
    return rows, leftover.hex(), sorted(boundaries)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archives", type=Path, default=Path("work/native/archives"))
    ap.add_argument("--agxparse", type=Path, required=True)
    ap.add_argument("--isa-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("raw/native_analysis.json"))
    ap.add_argument("--hex-dir", type=Path, default=Path("raw/hex"))
    args = ap.parse_args()
    agxparse = module("agxparse", args.agxparse.resolve())
    sys.path.insert(0, str(args.isa_dir.resolve()))
    import isadb

    args.hex_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    for archive in sorted(args.archives.glob("*.bin")):
        _, pieces = agxparse.extract_agx(archive.read_bytes())
        shader = pieces["_agc.main"]
        (args.hex_dir / f"{archive.stem}.hex").write_text(shader.hex() + "\n")
        rows, leftover, boundaries = decode(shader, isadb)
        result[archive.stem] = {
            "main_length": len(shader),
            "main_hex": shader.hex(),
            "leftover_hex": leftover,
            "instruction_boundaries": boundaries,
            "instructions": rows,
            "control_flow": [row for row in rows if row["mnemonic"] in CF],
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for name, record in result.items():
        print(f"\n{name}: len={record['main_length']} "
              f"leftover={len(bytes.fromhex(record['leftover_hex']))}")
        for row in record["control_flow"]:
            extra = ""
            if "signed_displacement" in row:
                extra = (f" disp={row['signed_displacement']:+d} "
                         f"targets={row['target_candidates']} "
                         f"boundary={row['candidate_is_boundary']}")
            print(f"  +{row['offset']:#05x} {row['mnemonic']:17s} "
                  f"{row['hex']} {row['fields']}{extra}")


if __name__ == "__main__":
    main()
