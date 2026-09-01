#!/usr/bin/env python3
"""Patch the native source-release/destination-publication cross over returns."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools/agx-isa"))
import isadb  # noqa: E402


CASES = (
    "r34_load_sequential_retain",
    "r34_texture_sequential_retain",
)


def load_agxparse():
    path = REPO / "tools/shdump/agxparse.py"
    spec = importlib.util.spec_from_file_location("r34_life_agxparse", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_field(data: bytearray, byte_offset: int, start: int,
                width: int, value: int) -> None:
    for bit in range(width):
        absolute = byte_offset * 8 + start + bit
        mask = 1 << (absolute & 7)
        if value & (1 << bit):
            data[absolute // 8] |= mask
        else:
            data[absolute // 8] &= ~mask


def main() -> int:
    agxparse = load_agxparse()
    capture_root = HERE / "captures/native-gap-forward"
    output_root = HERE / "generated/lifetime_ablations"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    case_map = {case["id"]: case for case in
                json.loads((HERE / "generated/cases.json").read_text())["cases"]}
    arms = []
    variants = {
        "native": 2,
        "release-source-early": 3,
        "suppress-destination-publication": 0,
    }
    for case_id in CASES:
        source_archive = capture_root / case_id / "archive.bin"
        archive = source_archive.read_bytes()
        location = agxparse.locate_region(archive, "_agc.main", "compute")
        if location is None:
            raise RuntimeError(f"{case_id}: no compute _agc.main")
        main_base, main_size = location
        main = archive[main_base:main_base + main_size]
        records = []
        offset = 0
        while offset < len(main):
            record, length = isadb.decode_one(main, offset)
            if record["mnemonic"] == "falu2i":
                raw = main[offset:offset + length]
                route = (int.from_bytes(raw, "little") >> 45) & 7
                if route != 0:
                    records.append((offset, length, record, raw, route))
            offset += length
        if len(records) < 2:
            raise RuntimeError(f"{case_id}: wanted two routed falu2i records")
        target_offset, target_length, target_record, before, route = records[0]
        if target_record["fields"]["opflags"] != 2:
            raise RuntimeError(
                f"{case_id}: first routed opflags drifted: "
                f"{target_record['fields']['opflags']}")
        for label, opflags in variants.items():
            body = bytearray(archive)
            absolute = main_base + target_offset
            patch_field(body, absolute, 20, 4, opflags)
            after = bytes(body[absolute:absolute + target_length])
            arm_id = f"{case_id}_{label}"
            output = output_root / f"{arm_id}.bin"
            output.write_bytes(body)
            arms.append({
                "id": arm_id,
                "case": case_id,
                "rule": label,
                "route": route,
                "native_route": route,
                "opflags": opflags,
                "native_opflags": 2,
                "expected": "exact" if label == "native" else None,
                "archive": str(output.relative_to(HERE)),
                "archive_sha256": sha(body),
                "instruction_offset": target_offset,
                "before": before.hex(),
                "after": after.hex(),
            })
    (output_root / "cases.json").write_text(json.dumps({
        "schema_version": 1,
        "cases": [case_map[case_id] for case_id in CASES],
    }, indent=2, sort_keys=True) + "\n")
    (output_root / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "scope": (
            "source release and destination publication on first routed "
            "consumption of a load or texture return"
        ),
        "arms": arms,
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"arms": len(arms), "cases": len(CASES)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
