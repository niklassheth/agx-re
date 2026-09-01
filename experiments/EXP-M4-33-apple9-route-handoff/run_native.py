#!/usr/bin/env python3
"""Execute EXP-M4-33 through the reviewed EXP-M4-29 native runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import re
import shutil
import time


HERE = pathlib.Path(__file__).resolve().parent
PARENT = HERE.parent / "EXP-M4-29-apple9-provenance-matrix"


def load_parent():
    spec = importlib.util.spec_from_file_location(
        "r33_native_base", PARENT / "run_native_matrix.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    module.HERE = HERE
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_id")
    parser.add_argument("order", choices=("forward", "reverse"))
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--match")
    args = parser.parse_args()
    base = load_parent()
    cases_doc = json.loads((HERE / "generated/cases.json").read_text())
    base.validate_case_files(cases_doc)
    cases = cases_doc["cases"]
    if args.order == "reverse":
        cases = list(reversed(cases))
    if args.match:
        pattern = re.compile(args.match)
        cases = [case for case in cases if pattern.search(case["id"])]
    root = HERE / "captures" / args.run_id
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HERE / "generated/cases.json", root / "case_manifest.json")
    records = []
    started = time.monotonic()
    for index, case in enumerate(cases):
        result = base.run_case(case, root, args.timeout)
        records.append(result)
        print(f"{index + 1}/{len(cases)} {case['id']} {result['outcome']}",
              flush=True)
    (root / "results.json").write_text(json.dumps({
        "schema_version": 1,
        "order": args.order,
        "elapsed_seconds": time.monotonic() - started,
        "records": records,
    }, indent=2, sort_keys=True) + "\n")
    failures = [record for record in records if record["outcome"] != "ok"]
    print(json.dumps({"cases": len(records), "failures": len(failures)},
                     sort_keys=True))
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
