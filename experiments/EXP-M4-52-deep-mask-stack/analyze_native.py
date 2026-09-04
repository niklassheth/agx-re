#!/usr/bin/env python3
"""Extract own-source mains and inventory deep control-flow encodings."""

import argparse
import collections
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


def decode(main, isadb):
    rows = []
    offset = 0
    while offset < len(main):
        try:
            rec, length = isadb.decode_one(main, offset)
            mnemonic = rec.get("op_mnemonic") or rec.get("mnemonic")
            fields = rec.get("fields", {})
        except ValueError as exc:
            # Deep probes add register pressure and therefore encounter several
            # still-undescribed Apple9 ALU forms.  Their lengths are nonetheless
            # known independently.  Retain each one as an opaque instruction so
            # a missing ALU descriptor cannot hide later mask-control records.
            length = isadb.instr_length(main, offset)
            if length is None or offset + length > len(main):
                return rows, main[offset:].hex()
            mnemonic = "<unknown>"
            fields = {"decode_error": str(exc)}
        encoded = main[offset:offset + length]
        rows.append({"offset": offset, "length": len(encoded),
                     "mnemonic": mnemonic, "hex": encoded.hex(),
                     "fields": fields})
        offset += len(encoded)
    return rows, ""


def scan_control(main):
    """Locate high-confidence mask records despite unrelated decoder gaps.

    Apple9 instructions are parcel-aligned.  Requiring the complete known
    leader plus the observed form byte makes these signatures specific enough
    for the nesting census; every tested depth must additionally contain an
    exactly balanced and structurally ordered set.
    """
    signatures = {
        b"\x0f\x05": ("if_push", 4, {0x54, 0x56}),
        b"\x0f\x04": ("mask_op", 4, {0x04, 0x24}),
        b"\x0f\x06": ("pop_reconverge", 6, {0x04, 0x24}),
        b"\x0f\x01": ("jump_cond", 10, {0x54, 0x64}),
    }
    rows = []
    for offset in range(0, len(main) - 3, 2):
        spec = signatures.get(main[offset:offset + 2])
        if spec is None:
            continue
        mnemonic, length, valid_form = spec
        if main[offset + 2] not in valid_form or offset + length > len(main):
            continue
        raw = main[offset:offset + length]
        rows.append({"offset": offset, "length": length,
                     "mnemonic": mnemonic, "hex": raw.hex(),
                     "form": raw[2], "kind": raw[3]})
    return rows


def predicates_before_push(main, control, isadb):
    """Find the closest described predicate compare preceding each push."""
    result = []
    for push in (row for row in control if row["mnemonic"] == "if_push"):
        candidates = []
        for offset in range(max(0, push["offset"] - 64), push["offset"], 2):
            try:
                rec, length = isadb.decode_one(main, offset)
            except ValueError:
                continue
            mnemonic = rec.get("op_mnemonic") or rec.get("mnemonic")
            if mnemonic == "icmp_pred" and offset + length <= push["offset"]:
                candidates.append((offset, rec))
        if not candidates:
            result.append(None)
            continue
        offset, rec = candidates[-1]
        encoded_predicate = rec["fields"].get("dst_pred")
        result.append({"offset": offset,
                       "distance_to_push": push["offset"] - offset,
                       "hex": rec["hex"],
                       # The DB's historical field name includes byte0's
                       # independently established inversion bit.  Separate it
                       # here before comparing predicate destinations.
                       "encoded_predicate_field": encoded_predicate,
                       "predicate_destination": (
                           encoded_predicate & ~1
                           if encoded_predicate is not None else None),
                       "predicate_invert": (
                           bool(encoded_predicate & 1)
                           if encoded_predicate is not None else None)})
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", type=Path, default=Path("work/native"))
    ap.add_argument("--agxparse", type=Path, required=True)
    ap.add_argument("--isa-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path,
                    default=Path("raw/native_analysis.json"))
    ap.add_argument("--hex-dir", type=Path, default=Path("raw/hex"))
    args = ap.parse_args()

    agxparse = module("agxparse", args.agxparse.resolve())
    sys.path.insert(0, str(args.isa_dir.resolve()))
    import isadb

    args.hex_dir.mkdir(parents=True, exist_ok=True)
    result = {"orders": {}, "cross_order": {}}
    for order in ("forward", "reverse"):
        records = {}
        archive_dir = args.workdir / f"archives-{order}"
        for archive in sorted(archive_dir.glob("nested_*.bin"),
                              key=lambda p: int(p.stem.split("_")[1])):
            _, pieces = agxparse.extract_agx(archive.read_bytes())
            shader = pieces["_agc.main"]
            (args.hex_dir / f"{order}-{archive.stem}.hex").write_text(
                shader.hex() + "\n")
            rows, leftover = decode(shader, isadb)
            decoded_control = [row for row in rows if row["mnemonic"] in CF]
            control = scan_control(shader)
            push_predicates = predicates_before_push(shader, control, isadb)
            partial_predicate_dsts = [
                row["fields"].get("dst_pred") for row in rows
                if row["mnemonic"] == "icmp_pred"]
            selector_counts = collections.Counter()
            for row in control:
                if row["mnemonic"] != "jump_cond":
                    selector_counts[
                        f"{row['mnemonic']}.form={row['form']:#04x}"
                        f".kind={row['kind']:#04x}"] += 1
            stack_depth = 0
            max_stack_depth = 0
            stack_underflow = False
            for row in control:
                if row["mnemonic"] == "if_push":
                    stack_depth += 1
                    max_stack_depth = max(max_stack_depth, stack_depth)
                elif row["mnemonic"] == "pop_reconverge":
                    stack_depth -= 1
                    stack_underflow |= stack_depth < 0
            records[archive.stem] = {
                "main_length": len(shader), "main_hex": shader.hex(),
                "leftover_hex": leftover, "instruction_count": len(rows),
                "partially_decoded_predicate_destinations": partial_predicate_dsts,
                "predicates_before_push": push_predicates,
                "selector_counts": dict(sorted(selector_counts.items())),
                "push_count": sum(row["mnemonic"] == "if_push" for row in control),
                "pop_count": sum(row["mnemonic"] == "pop_reconverge" for row in control),
                "max_push_depth": max_stack_depth,
                "balanced_push_pop": stack_depth == 0 and not stack_underflow,
                "control_flow": control,
                "partially_decoded_control_flow": decoded_control,
            }
        result["orders"][order] = records

    names = sorted(set(result["orders"]["forward"]) |
                   set(result["orders"]["reverse"]),
                   key=lambda name: int(name.split("_")[1]))
    for name in names:
        fwd = result["orders"]["forward"].get(name)
        rev = result["orders"]["reverse"].get(name)
        result["cross_order"][name] = {
            "present_both": fwd is not None and rev is not None,
            "main_identical": bool(fwd and rev and
                                   fwd["main_hex"] == rev["main_hex"]),
            "forward_length": fwd["main_length"] if fwd else None,
            "reverse_length": rev["main_length"] if rev else None,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    for name in names:
        row = result["orders"]["forward"].get(name)
        cross = result["cross_order"][name]
        if row is None:
            print(f"{name:10s} absent")
            continue
        print(f"{name:10s} len={row['main_length']:5d} "
              f"cf={len(row['control_flow']):3d} "
              f"stack={row['max_push_depth']:2d} "
              f"balanced={row['balanced_push_pop']} "
              f"order_equal={cross['main_identical']} "
              f"leftover={len(bytes.fromhex(row['leftover_hex']))}")
        print("  " + ", ".join(f"{key}:{value}" for key, value in
                               row["selector_counts"].items()))
        destinations = collections.Counter(
            pred["predicate_destination"] if pred is not None else None
            for pred in row["predicates_before_push"])
        print(f"  predicate destinations before pushes: {dict(destinations)}")


if __name__ == "__main__":
    main()
