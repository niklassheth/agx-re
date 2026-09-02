#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract one opaque eight-buffer carrier from a native trace manifest.

The executable archive and launch program remain opaque.  This tool only
uses public CDM geometry and the captured resource-address ledger to select
and normalize the caller-owned objects needed by the replay experiment.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct


CONTROL_GRID = [64, 1, 1]
CONTROL_LOCAL = [16, 1, 1]
VISIBLE_COUNT = 8


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture_map(item):
    return {capture["name"]: capture for capture in item["captures"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trace", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ordinal", type=int)
    args = parser.parse_args()

    trace = json.loads(args.trace.read_text())
    candidates = []
    for item in trace["items"]:
        if args.ordinal is not None and item["ordinal"] != args.ordinal:
            continue
        for dispatch in (item.get("package") or {}).get("dispatches", []):
            if (dispatch.get("global_size") == CONTROL_GRID and
                    dispatch.get("local_size") == CONTROL_LOCAL):
                candidates.append((item, dispatch))
    if len(candidates) != 1:
        raise SystemExit(
            "expected exactly one control dispatch; found %d (use --ordinal)" %
            len(candidates)
        )

    item, dispatch = candidates[0]
    arguments = dispatch.get("resource_arguments", [])
    if len(arguments) < 12:
        raise SystemExit("control capture did not include 12 resource qwords")
    visible = arguments[3:3 + VISIBLE_COUNT]
    if any(address == 0 for address in visible):
        raise SystemExit("one of the eight visible resource entries is zero")
    if arguments[11] != 0:
        raise SystemExit("resource entry 11 is not the expected zero sentinel")
    if arguments[0] + 12 != arguments[1]:
        raise SystemExit("hidden grid and unit-tuple pointers are not adjacent")

    captures = capture_map(item)
    required = {
        "archive.bin": "usc_archive",
        "launch.bin": "launch_00",
        "state.bin": "state_00",
        "resource.bin": "resource_00",
        "cdm.bin": "cdm_stream",
        "grid_page.bin": "argument_00_00",
        "arena_page.bin": "argument_00_02",
    }
    missing = [name for name in required.values() if name not in captures]
    if missing:
        raise SystemExit("capture is missing: %s" % ", ".join(missing))

    args.output.mkdir(parents=True, exist_ok=True)
    files = {}
    for destination, capture_name in required.items():
        capture = captures[capture_name]
        source = args.trace.parent / capture["file"]
        if sha256(source) != capture["sha256"]:
            raise SystemExit("capture hash mismatch: %s" % source)
        target = args.output / destination
        shutil.copyfile(source, target)
        files[destination] = {
            "dva": capture["dva"],
            "size": capture["size"],
            "sha256": capture["sha256"],
        }

    # The already-established archive grammar gives this wrapper's call
    # field and target without inspecting either executable semantically.
    # The 0x08aa call names archive main +0x440; the surrounding block starts
    # at +0x340 and its caller constant program occupies +0x380..+0x440.
    launch = (args.output / "launch.bin").read_bytes()
    archive = (args.output / "archive.bin").read_bytes()
    archive_call_offset = 0x8c
    archive_call = int.from_bytes(
        launch[archive_call_offset:archive_call_offset + 3], "little"
    )
    main_offset = 0x3c0 + (archive_call - 0x07aa) // 2
    if archive_call != 0x08aa or main_offset != 0x440:
        raise SystemExit("unexpected eight-buffer archive call relationship")
    block_offset = 0x340
    block_size = struct.unpack_from("<I", archive, block_offset)[0]
    constant_offset = block_offset + 0x40
    captured_constant = archive[constant_offset:main_offset]
    if block_size != 0x400 or len(captured_constant) != 0xc0:
        raise SystemExit("unexpected eight-buffer archive block layout")
    # A structural prefix/chop ablation with the largest Mesa main proves that
    # only the first 0x40 bytes need to be retained.  The launch call is
    # patched to the correspondingly earlier main by Mesa/the replay harness.
    constant = captured_constant[:0x40]
    constant_path = args.output / "constant.bin"
    constant_path.write_bytes(constant)
    files["constant.bin"] = {
        "dva": int(files["archive.bin"]["dva"]) + constant_offset,
        "size": len(constant),
        "sha256": hashlib.sha256(constant).hexdigest(),
    }

    # Native captures place an invariant reciprocal/division table at hidden
    # argument 2.  Only its first 8 KiB are needed; the remainder of the
    # captured page contains unrelated allocation-arena contents.
    arena = (args.output / "arena_page.bin").read_bytes()
    division = arena[:0x2000]
    if len(division) != 0x2000:
        raise SystemExit("captured hidden helper table is truncated")
    division_path = args.output / "division.bin"
    division_path.write_bytes(division)
    files["division.bin"] = {
        "dva": arguments[2],
        "size": len(division),
        "sha256": hashlib.sha256(division).hexdigest(),
    }

    normalized = {
        "schema": "agx-re.apple9-compute-superset-carrier.v1",
        "source": {
            "trace": str(args.trace),
            "ordinal": item["ordinal"],
            "doorbell_channel": item.get("doorbell_channel"),
            "pair": item.get("pair"),
        },
        "fixed_usc_base": item["package"]["usc_exec_base"],
        "control": {
            "grid": dispatch["global_size"],
            "local": dispatch["local_size"],
            "pipeline": dispatch["pipeline"],
            "resource_record": dispatch["resource_record"],
            "state": dispatch["state"],
        },
        "archive_block": {
            "block_offset": block_offset,
            "block_size": block_size,
            "constant_offset": constant_offset,
            "constant_size": len(constant),
            "captured_constant_size": len(captured_constant),
            "main_offset": main_offset,
            "launch_call_offset": archive_call_offset,
            "launch_call": archive_call,
        },
        "resource_layout": {
            "hidden_prefix_count": 3,
            "visible_start": 3,
            "visible_count": VISIBLE_COUNT,
            "zero_sentinel_index": 11,
            "arguments": arguments[:12],
        },
        "launch_pointer_fields": {
            "resource": [1, 4, 5, 6],
            "state": [17, 20, 21, 22],
        },
        "files": files,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(normalized, indent=2, sort_keys=True) + "\n"
    )
    print(
        "extracted ordinal=%d visible=%s output=%s" %
        (item["ordinal"], ",".join(hex(value) for value in visible),
         args.output)
    )


if __name__ == "__main__":
    main()
