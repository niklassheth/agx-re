#!/usr/bin/env python3
"""Patch only the route field of qualified native multi-source instructions."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import shutil
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PARENT = HERE.parent / "EXP-M4-29-apple9-provenance-matrix"
sys.path.insert(0, str(REPO / "tools/agx-isa"))
import isadb  # noqa: E402


CASES = {
    "r34_binary_load_load_direct": ("falu2", 45, 6, (6, 0, 1)),
    "r34_binary_texture_texture_direct": ("falu2", 45, 1, (1, 0, 2, 6)),
    "r34_binary_load_texture_direct": ("falu2", 45, 6, (6, 0, 1)),
    "r34_binary_texture_load_direct": ("falu2", 45, 6, (6, 0, 1)),
    "r34_fma_load_load_load_direct": ("falu3", 61, 6, (6, 0, 1)),
    "r34_fma_texture_texture_texture_direct": ("falu3", 61, 1, (1, 0, 2, 6)),
    "r34_fma_load_texture_load_direct": ("falu3", 61, 6, (6, 0, 1)),
}


def load_agxparse():
    path = REPO / "tools/shdump/agxparse.py"
    spec = importlib.util.spec_from_file_location("r34_agxparse", path)
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


def decode(data: bytes) -> list[dict]:
    records = []
    offset = 0
    while offset < len(data):
        record, length = isadb.decode_one(data, offset)
        records.append({
            "offset": offset,
            "length": length,
            "mnemonic": record["mnemonic"],
            "fields": record.get("fields", {}),
            "hex": data[offset:offset + length].hex(),
        })
        offset += length
    return records


def main() -> int:
    agxparse = load_agxparse()
    capture_root = HERE / "captures/native-forward"
    output_root = HERE / "generated/route_ablations"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    cases_doc = json.loads((HERE / "generated/cases.json").read_text())
    case_map = {case["id"]: case for case in cases_doc["cases"]}
    arms = []
    for case_id, (mnemonic, bit_start, native_route, routes) in CASES.items():
        source_archive = capture_root / case_id / "archive.bin"
        archive = source_archive.read_bytes()
        location = agxparse.locate_region(archive, "_agc.main", "compute")
        if location is None:
            raise RuntimeError(f"{case_id}: no compute _agc.main")
        main_base, main_size = location
        main = archive[main_base:main_base + main_size]
        candidates = [record for record in decode(main)
                      if record["mnemonic"] == mnemonic]
        if len(candidates) != 1:
            raise RuntimeError(
                f"{case_id}: wanted one {mnemonic}, found {len(candidates)}")
        target = candidates[0]
        observed = (int.from_bytes(bytes.fromhex(target["hex"]), "little") >>
                    bit_start) & 7
        if observed != native_route:
            raise RuntimeError(
                f"{case_id}: native route {observed}, expected {native_route}")
        for route in routes:
            body = bytearray(archive)
            target_absolute = main_base + target["offset"]
            before = bytes(body[target_absolute:
                                target_absolute + target["length"]])
            patch_field(body, target_absolute, bit_start, 3, route)
            after = bytes(body[target_absolute:
                               target_absolute + target["length"]])
            arm_id = f"{case_id}_route{route}"
            output = output_root / f"{arm_id}.bin"
            output.write_bytes(body)
            arms.append({
                "id": arm_id,
                "case": case_id,
                "rule": "native-control" if route == native_route else
                        "route-only-mutation",
                "route": route,
                "native_route": native_route,
                "expected": "exact" if route == native_route else None,
                "archive": str(output.relative_to(HERE)),
                "archive_sha256": sha(body),
                "source_archive": str(source_archive.relative_to(HERE)),
                "source_archive_sha256": sha(archive),
                "stage_main_offset": main_base,
                "stage_main_size": main_size,
                "instruction_offset": target["offset"],
                "instruction_mnemonic": mnemonic,
                "bit_start": bit_start,
                "before": before.hex(),
                "after": after.hex(),
            })

    selected_cases = [case_map[case_id] for case_id in CASES]
    (output_root / "cases.json").write_text(json.dumps({
        "schema_version": 1,
        "cases": selected_cases,
    }, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": 1,
        "scope": "focused route-only multi-source mutations; route 7 excluded",
        "arms": arms,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"arms": len(arms), "cases": len(CASES)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
