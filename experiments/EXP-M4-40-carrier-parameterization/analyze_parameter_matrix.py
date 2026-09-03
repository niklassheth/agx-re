#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the structural contracts in the T8132 carrier-parameter matrix.

This intentionally treats the Metal-generated launch programs as opaque byte
strings.  It compares public package structure and caller-owned pointers; it
does not decode the launch executable.
"""

import argparse
import json
from pathlib import Path
import struct


MARKER = bytes.fromhex("77002a41")
DYNAMIC_CASES = ((7082, 128), (7083, 256), (7084, 512), (7085, 1024))
STATIC_CASE = (7086, 128)


def capture_path(root, item, name):
    capture = next(entry for entry in item["captures"] if entry["name"] == name)
    return root / capture["file"]


def normalized(data, offset, size):
    result = bytearray(data)
    result[offset:offset + size] = bytes(size)
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "capture",
        nargs="?",
        type=Path,
        default=Path(__file__).parent / "raw" / "tgmem-param-01",
    )
    parser.add_argument(
        "--superset-carrier",
        type=Path,
        default=Path("/home/nsheth/Projects/asahi/tmp/agx-apple9/carrier8"),
    )
    args = parser.parse_args()

    manifest = json.loads((args.capture / "manifest.json").read_text())
    items = {int(item["ordinal"]): item for item in manifest["items"]}
    dynamic = []

    for ordinal, byte_count in DYNAMIC_CASES:
        item = items[ordinal]
        dispatch = item["package"]["dispatches"][0]
        assert dispatch["global_size"] == [64, 1, 1]
        assert dispatch["local_size"] == [32, 1, 1]

        launch = capture_path(args.capture, item, "launch_00").read_bytes()
        marker = launch.find(MARKER)
        assert marker >= 0 and launch.find(MARKER, marker + 1) < 0
        parameter_offset = marker + len(MARKER)
        parameter = struct.unpack_from("<I", launch, parameter_offset)[0]
        assert parameter == (byte_count << 2) | 0x80

        resource = capture_path(args.capture, item, "resource_00").read_bytes()
        record_offset = int(dispatch["resource_page_offset"])
        input_pointer, output_pointer = struct.unpack_from(
            "<QQ", resource, record_offset
        )
        dynamic.append({
            "ordinal": ordinal,
            "bytes": byte_count,
            "launch": launch,
            "marker": marker,
            "parameter_offset": parameter_offset,
            "parameter": parameter,
            "resource": resource,
            "record_offset": record_offset,
            "input_pointer": input_pointer,
            "output_pointer": output_pointer,
        })

    first = dynamic[0]
    for case in dynamic[1:]:
        assert case["marker"] == first["marker"]
        assert case["parameter_offset"] == first["parameter_offset"]
        assert normalized(case["launch"], case["parameter_offset"], 4) == \
            normalized(first["launch"], first["parameter_offset"], 4)
        assert case["record_offset"] == first["record_offset"]
        assert case["input_pointer"] == first["input_pointer"]
        assert normalized(case["resource"], case["record_offset"] + 8, 8) == \
            normalized(first["resource"], first["record_offset"] + 8, 8)

    for earlier, later in zip(dynamic, dynamic[1:]):
        assert later["output_pointer"] - earlier["output_pointer"] == 0x1000

    static_ordinal, static_bytes = STATIC_CASE
    static_item = items[static_ordinal]
    static_launch = capture_path(
        args.capture, static_item, "launch_00"
    ).read_bytes()
    static_marker = static_launch.find(MARKER)
    assert static_marker >= 0
    static_parameter = struct.unpack_from(
        "<I", static_launch, static_marker + len(MARKER)
    )[0]
    assert static_parameter == (static_bytes << 2) | 0x80

    superset_launch = (args.superset_carrier / "launch.bin").read_bytes()
    superset_marker = superset_launch.find(MARKER)
    assert superset_marker >= 0
    superset_parameter = struct.unpack_from(
        "<I", superset_launch, superset_marker + len(MARKER)
    )[0]

    print("dynamic threadgroup-memory allocation contract")
    for case in dynamic:
        print(
            "  ordinal=%d bytes=%d launch_word=%#x input=%#x output=%#x" % (
                case["ordinal"], case["bytes"], case["parameter"],
                case["input_pointer"], case["output_pointer"],
            )
        )
    print(
        "  launch bytes are identical after normalizing the one parameter "
        "word at +%#x" % first["parameter_offset"]
    )
    print(
        "  resource pages are identical after normalizing the caller output "
        "pointer at record+0x08"
    )
    print(
        "static control: ordinal=%d bytes=%d launch_word=%#x word_offset=%#x" % (
            static_ordinal, static_bytes, static_parameter,
            static_marker + len(MARKER),
        )
    )
    print(
        "eight-buffer carrier: current_word=%#x word_offset=%#x" % (
            superset_parameter, superset_marker + len(MARKER),
        )
    )


if __name__ == "__main__":
    main()
