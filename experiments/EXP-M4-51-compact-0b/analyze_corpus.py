#!/usr/bin/env python3
"""Census compact low-nibble-b records in the public Apple9 corpus.

The inputs are own/public-source Metal pipeline archives created by EXP-M4-32.
Only the caller-owned ``_agc.main`` shader region is examined.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "shdump"))
sys.path.insert(0, str(ROOT / "tools" / "agx-isa"))

import agxparse  # noqa: E402
import isadb  # noqa: E402


CAPTURE_ROOT = ROOT / "experiments" / "EXP-M4-32-public-metal-corpus" / "captures"
RUNS = (
    "native-metal4-v2",
    "native-metal4-pytorch-v2",
    "native-metal4-mlx-v1",
)


def compact_record(record: dict) -> dict:
    return {
        "hex": record.get("hex"),
        "mnemonic": record.get("mnemonic"),
        "op_mnemonic": record.get("op_mnemonic"),
        "fields": record.get("fields", {}),
        "error": record.get("error"),
    }


def main() -> int:
    archive_count = 0
    extraction_failures = []
    unique_mains: dict[str, tuple[bytes, list[str]]] = {}

    for run in RUNS:
        for archive in sorted((CAPTURE_ROOT / run).rglob("*.bin")):
            archive_count += 1
            try:
                _, pieces = agxparse.extract_agx(archive.read_bytes(), stage="compute")
                shader = pieces.get("_agc.main") if pieces else None
                if not shader:
                    raise ValueError("no compute _agc.main")
            except Exception as exc:  # Preserve every extraction failure in output.
                extraction_failures.append({"archive": str(archive), "error": str(exc)})
                continue

            digest = hashlib.sha256(shader).hexdigest()
            if digest not in unique_mains:
                unique_mains[digest] = (shader, [])
            unique_mains[digest][1].append(str(archive.relative_to(CAPTURE_ROOT)))

    exact_counts: Counter[str] = Counter()
    exact_programs: defaultdict[str, set[str]] = defaultdict(set)
    byte_counts = [Counter() for _ in range(4)]
    triples: Counter[str] = Counter()
    variant_programs: defaultdict[str, set[str]] = defaultdict(set)
    witnesses = []
    exact_0b000002 = []
    atomic_contexts = []
    atomic_predecessors: Counter[tuple[str, int, int]] = Counter()
    raw_atomic_predecessors: Counter[tuple[str, str, int, int, int]] = Counter()
    raw_atomic_examples = {}
    decoded_programs = 0
    complete_programs = 0

    for digest, (shader, archives) in unique_mains.items():
        # The table decoder is intentionally incomplete, so also locate the
        # well-established 14-byte device-atomic framing directly.  This
        # avoids losing atomics that occur after an unrelated decode gap.
        valid_atomic_ops = {
            0x10, 0x11, 0x12, 0x13, 0x14, 0x15,
            0x16, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
        }
        for offset in range(max(0, len(shader) - 13)):
            raw = shader[offset:offset + 14]
            if (len(raw) != 14 or raw[0] != 0x67 or raw[13] not in (0, 2) or
                raw[3] != 0 or raw[10] != 0 or raw[11] != 0):
                continue
            atomic_op = (raw[12] >> 1) & 0x1F
            if atomic_op not in valid_atomic_ops:
                continue
            dependency_mask = ((raw[1] >> 4) & 0x0F) | ((raw[2] & 3) << 4)
            predecessor_kind = "none"
            predecessor_hex = ""
            if (offset >= 10 and (shader[offset - 10] & 0x0F) == 0x0B and
                (shader[offset - 8] & 0x06) == 0x06):
                predecessor_kind = "long10"
                predecessor_hex = shader[offset - 10:offset].hex()
            elif offset >= 4 and (shader[offset - 4] & 0x0F) == 0x0B:
                predecessor_kind = "compact4"
                predecessor_hex = shader[offset - 4:offset].hex()
            key = (predecessor_kind, predecessor_hex, dependency_mask,
                   raw[9], atomic_op)
            raw_atomic_predecessors[key] += 1
            raw_atomic_examples.setdefault(key, {
                "main_sha256": digest,
                "archives": archives[:4],
                "offset": offset,
                "context": shader[max(0, offset - 16):offset + 22].hex(),
            })

        records, leftover = isadb.disassemble(shader)
        decoded_programs += bool(records)
        complete_programs += not leftover
        offsets = []
        offset = 0
        for record in records:
            offsets.append(offset)
            offset += record.get("length") or len(bytes.fromhex(record.get("hex", "")))

        for index, record in enumerate(records):
            raw = bytes.fromhex(record.get("hex", ""))
            if record.get("mnemonic") == "atomic_rmw" and len(raw) == 14:
                dependency_mask = ((raw[1] >> 4) & 0x0F) | ((raw[2] & 0x03) << 4)
                previous_raw = (
                    bytes.fromhex(records[index - 1].get("hex", ""))
                    if index else b""
                )
                previous_hex = previous_raw.hex()
                atomic_predecessors[(previous_hex, dependency_mask, raw[9])] += 1
                atomic_contexts.append({
                    "main_sha256": digest,
                    "archives": archives[:4],
                    "complete_decode": not leftover,
                    "offset": offsets[index],
                    "dependency_mask": dependency_mask,
                    "return_descriptor": raw[9],
                    "instruction": compact_record(record),
                    "previous": [
                        compact_record(r)
                        for r in records[max(0, index - 4):index]
                    ],
                    "next": [
                        compact_record(r)
                        for r in records[index + 1:index + 5]
                    ],
                    "following_16_bytes": shader[offsets[index] + 14:offsets[index] + 30].hex(),
                })

            if len(raw) != 4 or (raw[0] & 0x0F) != 0x0B:
                continue

            encoded = raw.hex()
            exact_counts[encoded] += 1
            exact_programs[encoded].add(digest)
            triples[raw[1:].hex()] += 1
            variant_programs[raw[1:].hex()].add(digest)
            for byte_index, value in enumerate(raw):
                byte_counts[byte_index][f"{value:02x}"] += 1

            witness = {
                "main_sha256": digest,
                "archives": archives[:4],
                "complete_decode": not leftover,
                "offset": offsets[index],
                "instruction": compact_record(record),
                "previous": [compact_record(r) for r in records[max(0, index - 4):index]],
                "next": [compact_record(r) for r in records[index + 1:index + 5]],
            }
            if encoded == "0b000002":
                exact_0b000002.append(witness)
            if len(witnesses) < 2000:
                witnesses.append(witness)

    output = {
        "scope": {
            "runs": list(RUNS),
            "archives": archive_count,
            "extraction_failures": extraction_failures,
            "unique_mains": len(unique_mains),
            "decoded_programs": decoded_programs,
            "complete_programs": complete_programs,
        },
        "compact_low_b_instances": sum(exact_counts.values()),
        "byte_histograms": [dict(c.most_common()) for c in byte_counts],
        "operand_triples": [
            {"bytes1_3": value, "instances": count,
             "programs": len(variant_programs[value])}
            for value, count in triples.most_common()
        ],
        "exact_encodings": [
            {"hex": value, "instances": count, "programs": len(exact_programs[value])}
            for value, count in exact_counts.most_common()
        ],
        "exact_0b000002": exact_0b000002,
        "atomic_predecessors": [
            {
                "previous_hex": previous,
                "dependency_mask": dependency,
                "return_descriptor": returned,
                "instances": count,
            }
            for (previous, dependency, returned), count
            in atomic_predecessors.most_common()
        ],
        "raw_atomic_predecessors": [
            {
                "predecessor_kind": kind,
                "predecessor_hex": previous,
                "dependency_mask": dependency,
                "return_descriptor": returned,
                "atomic_op": atomic_op,
                "instances": count,
                "example": raw_atomic_examples[
                    (kind, previous, dependency, returned, atomic_op)
                ],
            }
            for (kind, previous, dependency, returned, atomic_op), count
            in raw_atomic_predecessors.most_common()
        ],
        "atomic_contexts": atomic_contexts,
        "sample_witnesses": witnesses,
    }
    destination = Path(__file__).with_name("CORPUS_CENSUS.json")
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        **output["scope"],
        "compact_low_b_instances": output["compact_low_b_instances"],
        "unique_encodings": len(exact_counts),
        "exact_0b000002_instances": exact_counts["0b000002"],
        "exact_0b000002_programs": len(exact_programs["0b000002"]),
        "atomic_instances": len(atomic_contexts),
        "top_atomic_predecessors": output["atomic_predecessors"][:20],
        "raw_atomic_predecessors": output["raw_atomic_predecessors"][:40],
        "top_operand_triples": output["operand_triples"][:20],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
