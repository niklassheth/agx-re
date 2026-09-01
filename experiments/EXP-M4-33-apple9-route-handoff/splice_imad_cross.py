#!/usr/bin/env python3
"""Cross the two moving fields in EXP-M4-30's prior-return IMAD.

This operates only on an archive compiled from our own MSL.  It emits binary
test inputs plus a manifest; execution remains a separate, explicit step.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
R30 = HERE.parent / "EXP-M4-30-apple9-route-semantics"
CASE = "r30_iselect_atomic_u32_direct_route12_split_store_live0_a"
CAPTURE = R30 / "captures/native-route12d-forward" / CASE
AGXPARSE_PATH = REPO / "tools/shdump/agxparse.py"
OUTPUT = HERE / "generated/imad_cross"
IMAD_OFFSET = 200
NATIVE_IMAD = bytes.fromhex("9f10540002043200d0240200")


def load_agxparse():
    spec = importlib.util.spec_from_file_location("r33_agxparse", AGXPARSE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    agxparse = load_agxparse()
    archive = (CAPTURE / "archive.bin").read_bytes()
    location = agxparse.locate_region(archive, "_agc.main")
    if location is None:
        raise RuntimeError("_agc.main missing")
    main_base, main_size = location
    if IMAD_OFFSET + len(NATIVE_IMAD) > main_size:
        raise RuntimeError("IMAD range outside _agc.main")
    absolute = main_base + IMAD_OFFSET
    observed = archive[absolute:absolute + len(NATIVE_IMAD)]
    if observed != NATIVE_IMAD:
        raise RuntimeError(
            f"native IMAD drifted: {observed.hex()} != {NATIVE_IMAD.hex()}")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    variants = {
        "control": {},
        "b1hi_8_to_16": {1: 0x20},
        "srcB_4_to_8": {5: 0x08},
        "both": {1: 0x20, 5: 0x08},
    }
    manifest = {
        "schema_version": 1,
        "source_case": CASE,
        "source_archive_sha256": sha(archive),
        "imad_offset": IMAD_OFFSET,
        "native_imad": NATIVE_IMAD.hex(),
        "variants": {},
    }
    for name, replacements in variants.items():
        data = bytearray(archive)
        imad = bytearray(NATIVE_IMAD)
        for byte_offset, value in replacements.items():
            imad[byte_offset] = value
        data[absolute:absolute + len(imad)] = imad
        path = OUTPUT / f"{name}.archive.bin"
        path.write_bytes(data)
        manifest["variants"][name] = {
            "imad": bytes(imad).hex(),
            "archive": str(path.relative_to(HERE)),
            "archive_sha256": sha(data),
            "replacements": {str(key): value
                             for key, value in replacements.items()},
        }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"variants": len(variants),
                      "source_archive_sha256": sha(archive)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
