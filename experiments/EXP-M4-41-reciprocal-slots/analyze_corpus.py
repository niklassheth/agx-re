#!/usr/bin/env python3
"""Census native Metal's accurate Apple9 reciprocal instruction.

The input archives are all produced from public or project-authored Metal
source.  We walk only `_agc.main`, using the clean-room length oracle and
semantic decoder.  Unknown instruction *descriptors* do not stop the walk;
unknown instruction lengths do.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CORPUS = ROOT / "experiments/EXP-M4-32-public-metal-corpus/captures"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


agxparse = load_module(
    "agxparse_e41", ROOT / "experiments/EXP-0030-mesh/harness/agxparse.py"
)
isadb = load_module("isadb_e41", ROOT / "tools/agx-isa/isadb.py")


def archive_name(buf: bytes) -> str | None:
    """Read the public MTLB NAME tag without inspecting any executable blob."""
    pos = buf.find(b"NAME")
    if pos < 0 or pos + 6 > len(buf):
        return None
    size = int.from_bytes(buf[pos + 4 : pos + 6], "little")
    value = buf[pos + 6 : pos + 6 + size].rstrip(b"\0")
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError:
        return None


def walk(main: bytes):
    out = []
    off = 0
    while off < len(main):
        length = isadb.instr_length(main, off)
        if length is None or off + length > len(main):
            break
        raw = main[off : off + length]
        try:
            rec, _ = isadb.decode_one(main, off)
        except ValueError:
            rec = {"mnemonic": "<length-only>", "fields": {}, "hex": raw.hex()}
        rec = dict(rec)
        rec["offset"] = off
        rec["raw"] = raw
        out.append(rec)
        off += length
    return out, off


def scalar_load_slot(rec) -> int | None:
    if rec["mnemonic"] != "device_load" or len(rec["raw"]) != 14:
        return None
    raw = rec["raw"]
    t = ((raw[8] >> 6) << 1) | (raw[9] & 1)
    return {0: 1, 2: 2, 4: 3, 6: 4, 1: 5, 3: 6}.get(t)


def load_destination(rec) -> int | None:
    if rec["mnemonic"] != "device_load":
        return None
    return rec["fields"].get("extmode", -1) >> 1


def is_rcp(rec) -> bool:
    if rec["mnemonic"] != "fspecial":
        return False
    f = rec["fields"]
    return (
        f.get("fn_hi") == 1
        and (f.get("fnclass", -1) & 3) == 0
        # Byte 6 bit 4 is the source-release control, not part of the
        # reciprocal function selector.  Native code emits both 0x00
        # (retain) and 0x10 (last use) for the same arithmetic operation.
        and f.get("fnsel") in (0x00, 0x10)
        and f.get("precsel") == 0x48
    )


def small_record(rec):
    return {
        "offset": rec["offset"],
        "mnemonic": rec["mnemonic"],
        "hex": rec["raw"].hex(),
        "fields": rec.get("fields", {}),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--output", type=Path, default=HERE / "CORPUS_CENSUS.json")
    args = ap.parse_args()

    unique = {}
    origins = defaultdict(list)
    archive_count = 0
    extraction_failures = 0

    for path in sorted(args.corpus.rglob("*.bin")):
        archive_count += 1
        buf = path.read_bytes()
        try:
            _, pieces = agxparse.extract_agx(buf)
            main_bytes = pieces.get("_agc.main", b"") if pieces else b""
        except Exception:
            extraction_failures += 1
            continue
        if not main_bytes:
            extraction_failures += 1
            continue
        digest = hashlib.sha256(main_bytes).hexdigest()
        unique.setdefault(digest, main_bytes)
        origins[digest].append(
            {"archive": str(path.relative_to(args.corpus)), "name": archive_name(buf)}
        )

    field_counts = defaultdict(Counter)
    byte_counts = [Counter() for _ in range(10)]
    source_origin = Counter()
    source_load_slot = Counter()
    source_load_slot_by_handoff = Counter()
    handoff_release = Counter()
    handoff_result_desc = Counter()
    field_crosses = defaultdict(Counter)
    windows = []
    occurrences = 0
    weighted_occurrences = 0
    decoded_bytes = 0
    total_bytes = 0

    for digest, main_bytes in unique.items():
        recs, end = walk(main_bytes)
        decoded_bytes += end
        total_bytes += len(main_bytes)
        weight = len(origins[digest])
        for i, rec in enumerate(recs):
            if not is_rcp(rec):
                continue
            occurrences += 1
            weighted_occurrences += weight
            raw = rec["raw"]
            for n, value in enumerate(raw):
                byte_counts[n][value] += 1
            for key, value in rec["fields"].items():
                field_counts[key][value] += 1
            f = rec["fields"]
            handoff_release[(f["src_cache"], f["fnsel"])] += 1
            handoff_result_desc[(f["src_cache"], f["src_class"])] += 1
            for a, b in (
                ("src_cache", "src_class"),
                ("src_cache", "src_ext"),
                ("src_class", "src_ext"),
            ):
                field_crosses[f"{a}_x_{b}"][(f[a], f[b])] += 1

            src = rec["fields"]["src"] >> 2
            prior = None
            for candidate in reversed(recs[:i]):
                if load_destination(candidate) == src:
                    prior = candidate
                    break
            if prior is None:
                source_origin["no_prior_matching_scalar_load"] += 1
            else:
                source_origin["prior_matching_scalar_load"] += 1
                slot = scalar_load_slot(prior)
                source_load_slot[str(slot)] += 1
                source_load_slot_by_handoff[(f["src_cache"], slot)] += 1

            windows.append(
                {
                    "program_sha256": digest,
                    "origins": origins[digest][:4],
                    "weight": weight,
                    "rcp_index": i,
                    "rcp": small_record(rec),
                    "source_register": src,
                    "destination_register": rec["fields"]["dst"] >> 1,
                    "prior_matching_load": small_record(prior) if prior else None,
                    "prior_matching_load_slot": scalar_load_slot(prior) if prior else None,
                    "window": [small_record(x) for x in recs[max(0, i - 5) : i + 6]],
                }
            )

    result = {
        "input": str(args.corpus),
        "archives": archive_count,
        "extraction_failures": extraction_failures,
        "unique_mains": len(unique),
        "length_qualified_bytes": decoded_bytes,
        "total_main_bytes": total_bytes,
        "unique_rcp_occurrences": occurrences,
        "weighted_rcp_occurrences": weighted_occurrences,
        "field_counts": {
            key: {str(k): v for k, v in sorted(counts.items())}
            for key, counts in sorted(field_counts.items())
        },
        "field_crosses": {
            key: {f"{a},{b}": v for (a, b), v in sorted(counts.items())}
            for key, counts in sorted(field_crosses.items())
        },
        "byte_counts": {
            str(i): {str(k): v for k, v in sorted(counts.items())}
            for i, counts in enumerate(byte_counts)
        },
        "source_origin": dict(source_origin),
        "source_load_slot": dict(source_load_slot),
        "source_load_slot_by_handoff": {
            f"{handoff:#04x},slot-{slot}": count
            for (handoff, slot), count in sorted(source_load_slot_by_handoff.items())
        },
        "handoff_release": {
            f"{handoff:#04x},{release:#04x}": count
            for (handoff, release), count in sorted(handoff_release.items())
        },
        "handoff_result_desc": {
            f"{handoff:#04x},{desc:#04x}": count
            for (handoff, desc), count in sorted(handoff_result_desc.items())
        },
        "windows": windows,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: result[k] for k in result if k != "windows"}, indent=2))


if __name__ == "__main__":
    main()
