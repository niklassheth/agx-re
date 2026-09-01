#!/usr/bin/env python3
"""Generate a small native-Metal route-handoff corpus."""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import struct


HERE = pathlib.Path(__file__).resolve().parent
GENERATED = HERE / "generated"
WORDS = 1024
DISPATCH = 64
MASK32 = 0xFFFFFFFF


def u32(value: int) -> int:
    return value & MASK32


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def fbits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", f32(value)))[0]


def as_float(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", u32(value)))[0]


def input_word(buffer: int, lane: int) -> int:
    if buffer == 2:
        return u32(0x10203040 ^ lane * 0x01010101)
    raise KeyError(buffer)


def texture_f32(x: int, y: int) -> float:
    return f32((1 + x + 2 * y) / 16.0)


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def producer_value(kind: str, lane: int, role: int) -> float:
    if kind == "texture_f32":
        coordinate = (lane + role * 37) & 15
        return texture_f32(coordinate & 3, (coordinate >> 2) & 3)
    if kind == "atomic_f32":
        return as_float(input_word(2, (lane + role * 37) & (WORDS - 1)))
    raise KeyError(kind)


def apple9_input(value: float) -> float:
    bits = fbits(value)
    if (bits & 0x7F800000) == 0:
        return as_float(bits & 0x80000000)
    return value


def expected(case: dict) -> bytes:
    words = [0xCCCCCCCC] * WORDS
    for lane in range(DISPATCH):
        values = [producer_value(case["producer"], lane, role)
                  for role in range(2)]
        if case["producer"] == "atomic_f32":
            values = [apple9_input(value) for value in values]
        words[lane] = fbits(f32(values[0] + values[1]))
        for read_index in range(case["prior_count"]):
            factor = float(16 >> read_index)
            words[lane + DISPATCH * (read_index + 1)] = fbits(
                f32(values[case["prior_role"]] * factor))
    return struct.pack(f"<{WORDS}I", *words)


def producer_lines(kind: str, role: int, formulation: str) -> list[str]:
    p = f"p{role}"
    offset = role * 37
    if formulation == "a":
        index = f"((idx + {offset}u) & 1023u)"
    else:
        index = f"(({offset}u + idx) & 1023u)"
    if kind == "texture_f32":
        coordinate = f"((idx + {offset}u) & 15u)" if formulation == "a" \
            else f"(({offset}u + idx) & 15u)"
        return [
            f"uint c{role} = {coordinate};",
            f"float {p} = texf.read(uint2(c{role} & 3u, "
            f"(c{role} >> 2u) & 3u)).x;",
        ]
    if kind == "atomic_f32":
        return [
            f"float {p} = as_type<float>(atomic_fetch_add_explicit("
            f"&atom[{index}], 0u, memory_order_relaxed));"
        ]
    raise KeyError(kind)


def source(case: dict, formulation: str) -> str:
    lines: list[str] = []
    for role in case["issue_order"]:
        lines.extend(producer_lines(case["producer"], role, formulation))
    prior = case["prior_role"]
    for read_index in range(case["prior_count"]):
        factor = 16 >> read_index
        lines.append(f"float prior{read_index} = p{prior} * {factor}.0f;")
    lines.append("float result = p0 + p1;")
    for read_index in range(case["prior_count"]):
        lines.append(
            f"out[idx + {DISPATCH * (read_index + 1)}u] = "
            f"as_type<uint>(prior{read_index});"
        )
    lines.append("out[idx] = as_type<uint>(result);")
    texture_argument = ""
    if case["producer"] == "texture_f32":
        texture_argument = (
            "    texture2d<float, access::read> texf [[texture(1)]],\n"
        )
    atomic_argument = ""
    if case["producer"] == "atomic_f32":
        atomic_argument = "    device atomic_uint *atom [[buffer(2)]],\n"
    function = case["id"] + "_" + formulation
    body = "\n  ".join(lines)
    return f"""#include <metal_stdlib>
using namespace metal;
kernel void {function}(
    device const uint *in0 [[buffer(0)]],
{texture_argument}{atomic_argument}\
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]]) {{
  {body}
}}
"""


def definitions() -> list[dict]:
    cases = []
    for producer in ("texture_f32", "atomic_f32"):
        for issue_order in ((0, 1), (1, 0)):
            order_name = "01" if issue_order == (0, 1) else "10"
            for prior_role in (0, 1):
                cases.append({
                    "id": f"r33_{producer}_issue{order_name}_prior{prior_role}",
                    "producer": producer,
                    "issue_order": list(issue_order),
                    "prior_role": prior_role,
                    "prior_count": 1,
                })
        cases.append({
            "id": f"r33_{producer}_issue01_prior0_chain3",
            "producer": producer,
            "issue_order": [0, 1],
            "prior_role": 0,
            "prior_count": 3,
        })
    return cases


def main() -> int:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    (GENERATED / "sources").mkdir(parents=True)
    (GENERATED / "oracles").mkdir()
    native_cases = []
    definitions_list = definitions()
    for definition in definitions_list:
        oracle_path = GENERATED / "oracles" / f"{definition['id']}.bin"
        oracle_path.write_bytes(expected(definition))
        for formulation in ("a", "b"):
            case_id = definition["id"] + "_" + formulation
            source_path = GENERATED / "sources" / f"{case_id}.metal"
            source_path.write_text(source(definition, formulation))
            native_cases.append({
                **definition,
                "id": case_id,
                "cell_id": definition["id"],
                "formulation": formulation,
                "stage": "compute",
                "source": str(source_path.relative_to(HERE)),
                "compute_function": case_id,
                "expected": str(oracle_path.relative_to(HERE)),
                "expected_sha256": sha(oracle_path),
                "math_mode": "precise",
                "dispatch_threads": DISPATCH,
                "threads_per_threadgroup": DISPATCH,
            })
    cases_path = GENERATED / "cases.json"
    cases_path.write_text(json.dumps({
        "schema_version": 1,
        "scope": (
            "native Metal only; two async returns; route-bearing prior "
            "FALU2I then route-bearing binary FALU2; no device loads or "
            "instruction mutation"
        ),
        "cases": native_cases,
    }, indent=2, sort_keys=True) + "\n")
    files = []
    for path in sorted(GENERATED.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append({
                "path": str(path.relative_to(HERE)),
                "size": path.stat().st_size,
                "sha256": sha(path),
            })
    (GENERATED / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "files": files,
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"semantic_cases": len(definitions_list),
                      "native_cases": len(native_cases)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
