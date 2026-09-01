#!/usr/bin/env python3
"""Verify exact native outputs and Apple9 integer-logic slot masks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAPTURES = HERE / "captures/native"
sys.path.insert(0, str(REPO / "tools/agx-isa"))
import isadb  # noqa: E402


def load_agxparse():
    path = REPO / "tools/shdump/agxparse.py"
    spec = importlib.util.spec_from_file_location("r35_agxparse", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


AGXPARSE = load_agxparse()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def logic_pending_mask(raw: bytes) -> int:
    assert len(raw) == 10
    return ((raw[5] >> 5) & 0x7) | (((raw[7] >> 5) & 0x7) << 3)


def decode_main(archive: bytes) -> tuple[bytes, list[dict]]:
    _report, stages = AGXPARSE.extract_all_stages(archive)
    main = stages["compute"]["_agc.main"]
    records = []
    offset = 0
    while offset < len(main):
        record, length = isadb.decode_one(main, offset)
        raw = main[offset:offset + length]
        item = {
            "offset": offset,
            "length": length,
            "mnemonic": record["mnemonic"],
            "hex": raw.hex(),
            "fields": record.get("fields", {}),
        }
        if record["mnemonic"] == "ilogic":
            item["pending_mask"] = logic_pending_mask(raw)
        if record["mnemonic"] == "device_load":
            item["producer_token"] = f"{raw[8]:02x}{raw[9]:02x}"
        records.append(item)
        offset += length
    return main, records


def main() -> int:
    cases = {}
    for archive_path in sorted(CAPTURES.glob("*.archive.bin")):
        name = archive_path.name.removesuffix(".archive.bin")
        expected = (HERE / f"{name}.bin").read_bytes()
        output = (CAPTURES / f"{name}.output.bin").read_bytes()
        if output != expected:
            raise RuntimeError(f"{name}: complete output differs from oracle")
        archive = archive_path.read_bytes()
        stage_main, records = decode_main(archive)
        cases[name] = {
            "archive_sha256": sha(archive),
            "output_sha256": sha(output),
            "main_sha256": sha(stage_main),
            "main_size": len(stage_main),
            "records": records,
        }

    chain = cases["load_xor_chain6"]["records"]
    tokens = [r["producer_token"] for r in chain
              if r["mnemonic"] == "device_load"]
    masks = [r["pending_mask"] for r in chain if r["mnemonic"] == "ilogic"]
    if tokens != ["5101", "1100", "5100", "9100", "d100", "1101"]:
        raise RuntimeError(f"chain6 producer allocation drift: {tokens}")
    if masks != [0x20, 0x01, 0x02, 0x04, 0x08, 0x10]:
        raise RuntimeError(f"chain6 logic one-hot mask drift: {masks}")

    for name in ("load_xor_gid", "load_xor_load_distinct",
                 "load_xor_load_same"):
        masks = [r["pending_mask"] for r in cases[name]["records"]
                 if r["mnemonic"] == "ilogic"]
        if masks != [0x20]:
            raise RuntimeError(f"{name}: expected one direct slot-6 XOR: {masks}")

    result = {
        "schema_version": 1,
        "environment": {
            "chip": "T8132 Apple M4",
            "product_version": "26.6.2",
            "build_version": "25G83",
        },
        "logic_pending_mask_bits": {
            "slot1": 45,
            "slot2": 46,
            "slot3": 47,
            "slot4": 61,
            "slot5": 62,
            "slot6": 63,
        },
        "chain6_producer_tokens": tokens,
        "chain6_consumer_masks": [0x20, 0x01, 0x02, 0x04, 0x08, 0x10],
        "cases": cases,
    }
    (HERE / "RESULTS.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"EXP_M4_35_OK cases={len(cases)} exact_outputs={len(cases)} "
          "logic_slots=1,2,3,4,5,6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
