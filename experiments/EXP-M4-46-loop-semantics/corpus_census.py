#!/usr/bin/env python3
"""Census Apple9 branch encodings and branch-target bases in own-source corpus."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys


def signed48(value):
    return value - (1 << 48) if value & (1 << 47) else value


def category(name):
    lower = name.lower()
    for token in ("nested", "continue", "break", "while", "loop", "for_"):
        if token in lower:
            return token.rstrip("_")
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hex-dir", type=Path, required=True)
    ap.add_argument("--isa-dir", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=Path("raw/corpus_census.json"))
    args = ap.parse_args()
    sys.path.insert(0, str(args.isa_dir.resolve()))
    import isadb

    totals = Counter()
    forms = defaultdict(Counter)
    target_models = defaultdict(Counter)
    contexts = Counter()
    raw_control_forms = defaultdict(Counter)
    raw_control_examples = defaultdict(list)
    programs = []
    for path in sorted(args.hex_dir.glob("*.hex")):
        try:
            shader = bytes.fromhex(path.read_text().strip())
        except ValueError:
            continue

        # Keep a raw census alongside the decoded walk.  This is deliberately
        # limited to strong control-flow leaders so a bad length elsewhere in
        # the stream cannot hide the loop-latch forms we are studying.
        for off in range(len(shader)):
            label = None
            width = 0
            if shader[off:off + 2] in (bytes.fromhex("8f04"),
                                       bytes.fromhex("8f05")) and \
                    shader[off + 2:off + 3] in (b"\x54", b"\x56"):
                label = "8f_control"
                width = 6 if shader[off + 1] == 0x05 else 4
            elif shader[off:off + 2] == bytes.fromhex("0f05"):
                label, width = "mask_push", 4
            elif shader[off:off + 2] == bytes.fromhex("0f06"):
                label, width = "mask_pop", 6
            elif shader[off:off + 2] in (bytes.fromhex("0f00"),
                                         bytes.fromhex("0f01")):
                label, width = "mask_branch", 10
            if label is None or off + width > len(shader):
                continue
            form = shader[off:off + width].hex()
            raw_control_forms[label][form] += 1
            if len(raw_control_examples[(label, form)]) < 8:
                raw_control_examples[(label, form)].append({
                    "file": path.name,
                    "offset": off,
                })
        recs, leftover = isadb.disassemble(shader)
        rows, boundaries, offset = [], set(), 0
        for rec in recs:
            length = len(bytes.fromhex(rec["hex"]))
            mnemonic = rec.get("op_mnemonic") or rec.get("mnemonic")
            boundaries.add(offset)
            rows.append((offset, length, mnemonic, rec))
            offset += length
        boundaries.add(offset)
        pbranches = []
        for index, (off, length, mnemonic, rec) in enumerate(rows):
            if mnemonic not in ("jump", "jump_cond"):
                continue
            delta = signed48(rec["fields"]["offset"])
            targets = {
                "from_start": off + delta,
                "from_plus4": off + 4 + delta,
                "from_end": off + length + delta,
            }
            valid = {key: target in boundaries for key, target in targets.items()}
            totals[mnemonic] += 1
            forms[mnemonic][rec["hex"][4:6]] += 1
            for key, ok in valid.items():
                target_models[mnemonic][key + ("_hit" if ok else "_miss")] += 1
            prev = rows[index - 1][2] if index else "<start>"
            nxt = rows[index + 1][2] if index + 1 < len(rows) else "<end>"
            contexts[(mnemonic, prev, nxt)] += 1
            pbranches.append({
                "offset": off, "mnemonic": mnemonic, "hex": rec["hex"],
                "displacement": delta, "targets": targets,
                "target_is_boundary": valid, "previous": prev, "next": nxt,
            })
        if pbranches:
            programs.append({
                "file": path.name, "category": category(path.name),
                "main_length": len(shader), "decoded_length": offset,
                "leftover_length": len(leftover), "branches": pbranches,
            })

    output = {
        "hex_directory": str(args.hex_dir),
        "files_scanned": len(list(args.hex_dir.glob("*.hex"))),
        "programs_with_decoded_branches": len(programs),
        "branch_totals": dict(totals),
        "form_byte_histogram": {key: dict(value) for key, value in forms.items()},
        "target_model_counts": {key: dict(value) for key, value in target_models.items()},
        "neighbor_contexts": [
            {"mnemonic": key[0], "previous": key[1], "next": key[2], "count": value}
            for key, value in contexts.most_common()
        ],
        "raw_control_forms": {
            label: [
                {
                    "hex": form,
                    "count": count,
                    "examples": raw_control_examples[(label, form)],
                }
                for form, count in counts.most_common()
            ]
            for label, counts in raw_control_forms.items()
        },
        "programs": programs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in (
        "files_scanned", "programs_with_decoded_branches", "branch_totals",
        "form_byte_histogram", "target_model_counts")}, indent=2))
    print("\nMost common branch neighborhoods:")
    for row in output["neighbor_contexts"][:20]:
        print(f"  {row['count']:4d} {row['previous']:18s} -> "
              f"{row['mnemonic']:10s} -> {row['next']}")


if __name__ == "__main__":
    main()
