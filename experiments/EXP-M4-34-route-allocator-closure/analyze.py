#!/usr/bin/env python3
"""Qualify native assembly and exact hardware results for EXP-M4-34."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import struct
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools/agx-isa"))
import isadb  # noqa: E402


RUN_PAIRS = (
    ("native-forward", "native-reverse"),
    ("native-gap-forward", "native-gap-reverse"),
    ("native-mixed-forward", "native-mixed-reverse"),
    ("native-refill-forward", "native-refill-reverse"),
    ("native-texture-refill-forward", "native-texture-refill-reverse"),
)


def load_agxparse():
    path = REPO / "tools/shdump/agxparse.py"
    spec = importlib.util.spec_from_file_location("r34_analyze_agxparse", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


AGXPARSE = load_agxparse()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main_bytes(case_root: pathlib.Path) -> bytes:
    archive = (case_root / "archive.bin").read_bytes()
    _report, stages = AGXPARSE.extract_all_stages(archive)
    return stages["compute"]["_agc.main"]


def records(data: bytes) -> list[dict]:
    output = []
    offset = 0
    while offset < len(data):
        record, length = isadb.decode_one(data, offset)
        raw = data[offset:offset + length]
        item = {
            "offset": offset,
            "length": length,
            "mnemonic": record["mnemonic"],
            "fields": record.get("fields", {}),
            "hex": raw.hex(),
        }
        if record["mnemonic"] in ("falu2", "falu2i"):
            item["route"] = (int.from_bytes(raw, "little") >> 45) & 7
        elif record["mnemonic"] == "falu3":
            item["route"] = (int.from_bytes(raw, "little") >> 61) & 7
        output.append(item)
        offset += length
    return output


def result(root: pathlib.Path, case_id: str) -> dict:
    return json.loads((root / case_id / "result.json").read_text())


def route_sequence(entry: dict, mnemonic: str | None = None) -> list[int]:
    return [record["route"] for record in entry["records"]
            if "route" in record and
            (mnemonic is None or record["mnemonic"] == mnemonic)]


def exact_native_census(cases: dict[str, dict]) -> tuple[dict, int]:
    entries = {}
    executions = 0
    for forward_name, reverse_name in RUN_PAIRS:
        forward_root = HERE / "captures" / forward_name
        reverse_root = HERE / "captures" / reverse_name
        forward_doc = json.loads((forward_root / "results.json").read_text())
        reverse_doc = json.loads((reverse_root / "results.json").read_text())
        forward_ids = [record["case"] for record in forward_doc["records"]]
        reverse_ids = [record["case"] for record in reverse_doc["records"]]
        if set(forward_ids) != set(reverse_ids):
            raise RuntimeError(f"run pair differs: {forward_name}/{reverse_name}")
        for case_id in forward_ids:
            if case_id in entries:
                raise RuntimeError(f"case captured by multiple run pairs: {case_id}")
            case = cases[case_id]
            expected = (HERE / case["expected"]).read_bytes()
            forward = result(forward_root, case_id)
            reverse = result(reverse_root, case_id)
            if forward["outcome"] != "ok" or reverse["outcome"] != "ok":
                raise RuntimeError(f"{case_id}: native execution not exact")
            if forward["output_sha256"] != sha(expected) or \
                    reverse["output_sha256"] != sha(expected):
                raise RuntimeError(f"{case_id}: output does not match oracle")
            forward_main = main_bytes(forward_root / case_id)
            reverse_main = main_bytes(reverse_root / case_id)
            if forward_main != reverse_main:
                raise RuntimeError(f"{case_id}: forward/reverse main differs")
            entries[case_id] = {
                "case": case,
                "run_pair": [forward_name, reverse_name],
                "main_sha256": sha(forward_main),
                "main_size": len(forward_main),
                "records": records(forward_main),
                "expected_sha256": sha(expected),
            }
            executions += 2
    return entries, executions


def assert_routes(entries: dict) -> dict:
    for kind, head in (("load", 6), ("texture", 1)):
        allocation = [6, 1, 2, 3, 4] if kind == "load" else [1, 2, 3, 4, 5]
        for count in (1, 2, 3, 5):
            case_id = f"r34_{kind}_chain{count}"
            observed = route_sequence(entries[case_id], "falu2i")
            if observed != allocation[:count]:
                raise RuntimeError(f"{case_id}: route drift {observed}")
        fanout = route_sequence(entries[f"r34_{kind}_fanout3"], "falu2i")
        if fanout != [head, 0, 0]:
            raise RuntimeError(f"{kind} fanout drift: {fanout}")
        sequential = route_sequence(
            entries[f"r34_{kind}_sequential_retain"], "falu2i")
        if sequential != [head, head, 0]:
            raise RuntimeError(f"{kind} sequential drift: {sequential}")

    mixed_expected = {
        "r34_mixed_chain_load_load_texture": [6, 2, 1],
        "r34_mixed_chain_load_texture_load": [6, 1, 2],
        "r34_mixed_chain_texture_load_load": [1, 6, 2],
        "r34_mixed_chain_texture_texture_load": [1, 2, 6],
        "r34_mixed_chain_texture_load_texture": [1, 6, 2],
        "r34_mixed_chain_load_texture_texture": [6, 1, 2],
    }
    for case_id, expected in mixed_expected.items():
        observed = route_sequence(entries[case_id], "falu2i")
        if observed != expected:
            raise RuntimeError(f"{case_id}: mixed route drift {observed}")

    direct_expected = {
        "r34_binary_load_load_direct": 6,
        "r34_binary_texture_texture_direct": 1,
        "r34_binary_load_texture_direct": 6,
        "r34_binary_texture_load_direct": 6,
        "r34_fma_load_load_load_direct": 6,
        "r34_fma_texture_texture_texture_direct": 1,
        "r34_fma_load_texture_load_direct": 6,
    }
    for case_id, expected in direct_expected.items():
        values = route_sequence(entries[case_id])
        target_mnemonic = "falu3" if case_id.startswith("r34_fma") else "falu2"
        values = [record["route"] for record in entries[case_id]["records"]
                  if record["mnemonic"] == target_mnemonic]
        if values != [expected]:
            raise RuntimeError(f"{case_id}: multi-source route drift {values}")

    reuse = {
        "load_gap3_free2": route_sequence(
            entries["r34_load_vgap3_free2"], "falu2i"),
        "load_gap_refill_free2": route_sequence(
            entries["r34_load_gap_refill_free2"]),
        "texture_gap_refill_free2": route_sequence(
            entries["r34_texture_gap_refill_free2"]),
    }
    if reuse["load_gap3_free2"] != [6, 1, 2, 6]:
        raise RuntimeError(f"load gap reuse drift: {reuse}")
    if reuse["load_gap_refill_free2"] != [6, 1, 2, 6]:
        raise RuntimeError(f"load refill drift: {reuse}")
    if reuse["texture_gap_refill_free2"] != [1, 2, 1, 2]:
        raise RuntimeError(f"texture refill drift: {reuse}")
    return {
        "load_allocation_order": [6, 1, 2, 3, 4, 5],
        "texture_allocation_order": [1, 2, 3, 4, 5, 6],
        "mixed_routes": mixed_expected,
        "direct_multi_source_routes": direct_expected,
        "reuse_route_sequences": reuse,
    }


def mutation_census(suite: str, run_id: str) -> dict:
    root = HERE / "captures" / suite / run_id
    doc = json.loads((root / "results.json").read_text())
    counts = {}
    details = []
    for record in doc["records"]:
        counts[record["outcome"]] = counts.get(record["outcome"], 0) + 1
        case_root = root / record["arm"] / f"repeat-{record['repetition']}"
        expected = (case_root / "expected.bin").read_bytes()
        output = (case_root / "output.bin").read_bytes()
        expected_words = struct.unpack("<1024I", expected)
        output_words = struct.unpack("<1024I", output)
        differences = [index for index, pair in
                       enumerate(zip(expected_words, output_words))
                       if pair[0] != pair[1]]
        details.append({
            **record,
            "different_words": len(differences),
            "different_word_range": ([min(differences), max(differences)]
                                     if differences else None),
            "changed_words_all_zero":
                bool(differences) and all(output_words[index] == 0
                                          for index in differences),
        })
    return {"counts": counts, "records": details}


def main() -> int:
    cases = {case["id"]: case for case in
             json.loads((HERE / "generated/cases.json").read_text())["cases"]}
    entries, native_executions = exact_native_census(cases)
    model = assert_routes(entries)
    route_mutations = mutation_census("route-ablations", "focused-1")
    lifetime_mutations = mutation_census("lifetime-ablations", "focused-1")

    nonnative_route = [record for record in route_mutations["records"]
                       if record["route"] != record["native_route"]]
    if not nonnative_route or any(
            record["outcome"] != "changed_output" or
            record["different_words"] != 64 or
            record["different_word_range"] != [0, 63] or
            not record["changed_words_all_zero"]
            for record in nonnative_route):
        raise RuntimeError("route mutation sensitivity signature drifted")
    early_release = [record for record in lifetime_mutations["records"]
                     if record["rule"] == "release-source-early"]
    if any(record["outcome"] != "changed_output" or
           record["different_words"] != 64 or
           record["different_word_range"] != [128, 191] or
           not record["changed_words_all_zero"]
           for record in early_release):
        raise RuntimeError("early release signature drifted")
    suppress_publication = [record for record in lifetime_mutations["records"]
                            if record["rule"] ==
                            "suppress-destination-publication"]
    if any(record["outcome"] != "exact"
           for record in suppress_publication):
        raise RuntimeError("publication-bit carrier signature drifted")

    output = {
        "schema_version": 1,
        "environment": {
            "target": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "summary": {
            "assembly_qualified_native_cases": len(entries),
            "exact_native_executions": native_executions,
            "route_mutation_executions": len(route_mutations["records"]),
            "lifetime_mutation_executions": len(lifetime_mutations["records"]),
            "total_hardware_executions": native_executions +
                                         len(route_mutations["records"]) +
                                         len(lifetime_mutations["records"]),
        },
        "allocator_model": model,
        "route_mutations": route_mutations,
        "lifetime_mutations": lifetime_mutations,
        "cases": entries,
    }
    (HERE / "RESULTS.json").write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps(output["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
