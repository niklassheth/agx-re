#!/usr/bin/env python3
"""Test multi-bit waits with two distinguishable pending load groups."""

from __future__ import annotations

import json

import run_cross_remote as cross
import run_remote as common


SCHEDULES = ((6, 1), (1, 6), (2, 5), (3, 4))


def main() -> int:
    function = "iadd_load"
    spec = {
        "consumer": 0x20,
        "buffers": {
            0: [0] * 4,
            1: [100, 200, 300, 400],
            2: [1, 2, 3, 4],
        },
        "oracle": [101, 202, 303, 404],
    }
    native = cross.main_bytes(function, spec)
    records = []
    for first_slot, second_slot in SCHEDULES:
        first_mask = 1 << (first_slot - 1)
        second_mask = 1 << (second_slot - 1)
        for relation, mask in (
                ("zero", 0),
                ("first", first_mask),
                ("second", second_mask),
                ("both", first_mask | second_mask)):
            splices = [
                f"_agc.main@0xc={cross.TOKENS[first_slot]}",
                f"_agc.main@0x1a={cross.TOKENS[second_slot]}",
                cross.field_splice(spec["consumer"], native, mask),
            ]
            result = cross.execute(function, spec, splices)
            record = {
                "first_slot": first_slot,
                "second_slot": second_slot,
                "consumer_mask": mask,
                "relation": relation,
                **result,
            }
            records.append(record)
            print(f"schedule={first_slot}-{second_slot} mask={mask:02x} "
                  f"relation={relation:6} exact={int(result['exact'])} "
                  f"values={result['values']}", flush=True)

    (common.ROOT / "MIXED_RESULTS.json").write_text(json.dumps({
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "records": records,
    }, indent=2, sort_keys=True) + "\n")
    print(f"SUMMARY records={len(records)} "
          f"exact={sum(record['exact'] for record in records)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
