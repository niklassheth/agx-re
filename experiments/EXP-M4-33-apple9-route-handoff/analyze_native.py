#!/usr/bin/env python3
"""Qualify the prior and later route-bearing consumers in EXP-M4-33."""

from __future__ import annotations

import collections
import hashlib
import importlib.util
import json
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
PARENT = HERE.parent / "EXP-M4-29-apple9-provenance-matrix"
UNKNOWN_ATOMIC_BRIDGE = bytes.fromhex("0b000022")


def load_parent():
    spec = importlib.util.spec_from_file_location(
        "r33_archive_base", PARENT / "analyze.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stage_main(base, case: dict, root: pathlib.Path) -> bytes:
    archive = (root / case["id"] / "archive.bin").read_bytes()
    _report, stages = base.agxparse.extract_all_stages(archive)
    return stages["compute"]["_agc.main"]


def tokenize(base, data: bytes) -> list[dict]:
    records = []
    offset = 0
    while offset < len(data):
        try:
            record, length = base.isadb.decode_one(data, offset)
        except ValueError:
            if data[offset:offset + 4] != UNKNOWN_ATOMIC_BRIDGE:
                raise
            length = 4
            record = {
                "mnemonic": "atomic_return_bridge_unknown",
                "op_mnemonic": None,
                "fields": {},
                "note": "bounded own-source atomic return bridge",
            }
        records.append({
            "offset": offset,
            "length": length,
            "mnemonic": record["mnemonic"],
            "op_mnemonic": record.get("op_mnemonic"),
            "hex": data[offset:offset + length].hex(),
            "fields": record.get("fields", {}),
            "note": record.get("note"),
        })
        offset += length
    return records


def route(record: dict) -> dict:
    raw = bytes.fromhex(record["hex"])
    value = (int.from_bytes(raw, "little") >> 45) & 7
    cleared = bytearray(raw)
    cleared[5] &= 0x1F
    return {
        "value": value,
        "start": 45,
        "width": 3,
        "without_route": bytes(cleared).hex(),
    }


def execution(root: pathlib.Path, case_id: str) -> dict:
    return json.loads((root / case_id / "result.json").read_text())


def main() -> int:
    base = load_parent()
    cases = json.loads((HERE / "generated/cases.json").read_text())["cases"]
    forward_root = HERE / "captures/native-forward"
    reverse_root = HERE / "captures/native-reverse"
    entries = {}
    for case in cases:
        forward = execution(forward_root, case["id"])
        reverse = execution(reverse_root, case["id"])
        expected_sha = sha((HERE / case["expected"]).read_bytes())
        if any(item["outcome"] != "ok" or
               item["output_sha256"] != expected_sha
               for item in (forward, reverse)):
            raise RuntimeError(f"{case['id']}: non-exact execution")
        forward_main = stage_main(base, case, forward_root)
        reverse_main = stage_main(base, case, reverse_root)
        if forward_main != reverse_main:
            raise RuntimeError(f"{case['id']}: compilation-order instability")
        records = tokenize(base, forward_main)
        priors = [record for record in records
                  if record["mnemonic"] == "falu2i" and
                  record["fields"].get("opsel") == 5]
        targets = [record for record in records
                   if record["mnemonic"] == "falu2" and
                   record["fields"].get("opsel") == 4]
        if len(priors) != case["prior_count"] or len(targets) != 1:
            raise RuntimeError(
                f"{case['id']}: wanted {case['prior_count']} prior FALU2I "
                "records and one target FALU2; "
                f"got {priors}, {targets}")
        target = targets[0]
        if any(prior["offset"] >= target["offset"] for prior in priors):
            raise RuntimeError(f"{case['id']}: prior consumer scheduled late")
        last_prior = priors[-1]
        between = [record for record in records
                   if last_prior["offset"] + last_prior["length"] <=
                   record["offset"] <
                   target["offset"]]
        entries[case["id"]] = {
            "case": case,
            "main_sha256": sha(forward_main),
            "main_size": len(forward_main),
            "priors": priors,
            "prior_routes": [route(prior) for prior in priors],
            "between": between,
            "target": target,
            "target_route": route(target),
        }

    cells = collections.defaultdict(dict)
    for entry in entries.values():
        cells[entry["case"]["cell_id"]][entry["case"]["formulation"]] = entry
    for cell, pair in cells.items():
        if set(pair) != {"a", "b"} or \
                pair["a"]["main_sha256"] != pair["b"]["main_sha256"]:
            raise RuntimeError(f"{cell}: formulation instability")

    semantic = {}
    for cell, pair in sorted(cells.items()):
        entry = pair["a"]
        semantic[cell] = {
            "producer": entry["case"]["producer"],
            "issue_order": entry["case"]["issue_order"],
            "prior_role": entry["case"]["prior_role"],
            "prior_count": entry["case"]["prior_count"],
            "prior_routes": [item["value"]
                             for item in entry["prior_routes"]],
            "prior_hex": [item["hex"] for item in entry["priors"]],
            "prior_fields": [item["fields"] for item in entry["priors"]],
            "target_route": entry["target_route"]["value"],
            "target_hex": entry["target"]["hex"],
            "target_fields": entry["target"]["fields"],
            "between": entry["between"],
        }
    output = {
        "schema_version": 1,
        "environment": {
            "target": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "summary": {
            "native_cases": len(cases),
            "exact_executions": len(cases) * 2,
            "stable_formulation_pairs": len(cells),
        },
        "semantic_handoffs": semantic,
        "cases": entries,
    }
    (HERE / "NATIVE_CENSUS.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output["summary"], sort_keys=True))
    for cell, item in semantic.items():
        print(cell, "priors", item["prior_routes"], "target",
              item["target_route"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
