#!/usr/bin/env python3
"""Census high-confidence native load -> direct-store pairs in EXP-M4-32."""

from __future__ import annotations

import collections
import json
import pathlib
import subprocess


HERE = pathlib.Path(__file__).resolve().parent
CORPUS = (HERE.parent / "EXP-M4-32-public-metal-corpus" /
          "ASSEMBLY.jsonl.zst")


def main() -> int:
    inverse_slot_token = {(2 * (slot - 1)) % 7: slot
                          for slot in range(1, 7)}
    slots = collections.Counter()
    formats = collections.Counter()
    unique_pairs = 0
    weighted_occurrences = 0
    examples = []

    process = subprocess.Popen(
        ["zstdcat", str(CORPUS)], stdout=subprocess.PIPE, text=True)
    assert process.stdout is not None
    for line in process.stdout:
        program = json.loads(line)
        records = program["records"]
        for load, store in zip(records, records[1:]):
            if (load.get("mnemonic") != "device_load" or
                store.get("mnemonic") != "device_store"):
                continue
            load_fields = load.get("fields") or {}
            store_fields = store.get("fields") or {}
            if store_fields.get("addr_mode") != 0x56:
                continue

            # A high-confidence direct pair is adjacent, names the same
            # destination half-register, and uses matching load/store formats.
            # Broader 0x56 adjacency includes known decoder collisions and is
            # deliberately excluded from this compiler-facing census.
            if load_fields.get("extmode") != store_fields.get("extmode"):
                continue
            if load_fields.get("ld_format") != store_fields.get("st_format"):
                continue

            token = (2 * load_fields["dst_lo"] +
                     (load_fields["dst_ext9"] & 1))
            slot = inverse_slot_token.get(token, "unknown")
            unique_pairs += 1
            weighted_occurrences += len(program.get("occurrences", []))
            slots[str(slot)] += 1
            formats[str(load_fields["ld_format"])] += 1
            if len(examples) < 12:
                examples.append({
                    "program_sha256": program["sha256"],
                    "offset": load["offset"],
                    "slot": slot,
                    "load": load["hex"],
                    "store": store["hex"],
                    "occurrences": len(program.get("occurrences", [])),
                })
    if process.wait() != 0:
        raise SystemExit("zstdcat failed")

    result = {
        "schema_version": 1,
        "selection": {
            "adjacent": True,
            "store_addr_mode": 0x56,
            "same_half_register_selector": True,
            "matching_load_store_format": True,
        },
        "unique_pairs": unique_pairs,
        "weighted_native_occurrences": weighted_occurrences,
        "slots": dict(sorted(slots.items())),
        "formats": dict(sorted(formats.items(), key=lambda item: int(item[0]))),
        "examples": examples,
    }
    path = HERE / "NATIVE_DIRECT_PAIR_CENSUS.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
