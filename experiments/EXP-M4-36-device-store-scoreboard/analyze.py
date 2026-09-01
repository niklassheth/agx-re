#!/usr/bin/env python3
"""Summarize the selector hypotheses from a completed EXP-M4-36 run."""

from __future__ import annotations

import argparse
import collections
import json
import pathlib


HERE = pathlib.Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    args = parser.parse_args()
    data = json.loads((HERE / "captures" / args.run_id / "results.json").read_text())
    grouped = collections.defaultdict(list)
    for record in data["records"]:
        grouped[record["case"]].append(record)
    summary = []
    for case_id, records in grouped.items():
        outputs = collections.Counter(tuple(record["observed"] or [])
                                      for record in records)
        summary.append({
            "case": case_id,
            "outcomes": dict(collections.Counter(record["outcome"]
                                                  for record in records)),
            "outputs": {str(list(key)): count for key, count in outputs.items()},
            "all_canaries": all(record["canary_ok"] for record in records),
        })
    out = {
        "run_id": args.run_id,
        "cases": summary,
        "all_associative": all(
            all(record["outcome"] == "exact_associative" for record in records)
            for records in grouped.values()),
    }
    path = HERE / "captures" / args.run_id / "summary.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
