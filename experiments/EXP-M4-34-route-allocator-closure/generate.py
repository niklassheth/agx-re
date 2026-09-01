#!/usr/bin/env python3
"""Generate bounded native-Metal route allocator and multi-source cases."""

from __future__ import annotations

import hashlib
import json
import math
import pathlib
import shutil
import struct


HERE = pathlib.Path(__file__).resolve().parent
GENERATED = HERE / "generated"
WORDS = 1024
DISPATCH = 64
MASK32 = 0xFFFFFFFF


def f32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", value))[0]


def fbits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", f32(value)))[0]


def load_value(index: int) -> float:
    return f32(((index % 13) + 1) / 16.0)


def texture_value(coordinate: int) -> float:
    coordinate &= 15
    x = coordinate & 3
    y = (coordinate >> 2) & 3
    return f32((1 + x + 2 * y) / 16.0)


def producer_value(kind: str, lane: int, role: int) -> float:
    offset = role * 37
    if kind == "load":
        return load_value((lane + offset) & (WORDS - 1))
    if kind == "texture":
        return texture_value((lane + offset) & 15)
    raise KeyError(kind)


def producer_expr(kind: str, role: int, dynamic: str | None = None) -> str:
    if dynamic is None:
        index = f"((idx + {role * 37}u) & 1023u)"
        coordinate = f"((idx + {role * 37}u) & 15u)"
    else:
        index = f"((idx + {role * 37}u + {dynamic}) & 1023u)"
        coordinate = f"((idx + {role * 37}u + {dynamic}) & 15u)"
    if kind == "load":
        return f"in0[{index}]"
    if kind == "texture":
        return f"texf.read(uint2({coordinate} & 3u, ({coordinate} >> 2u) & 3u)).x"
    raise KeyError(kind)


def make_source(case: dict) -> str:
    kind = case.get("kind")
    shape = case["shape"]
    lines: list[str] = []

    if shape == "fanout":
        lines.append(f"float p0 = {producer_expr(kind, 0)};")
        for read, factor in enumerate((16, 8, 4)):
            lines.append(f"float q{read} = p0 * {factor}.0f;")
        for read in range(3):
            lines.append(
                f"out[idx + {read * DISPATCH}u] = as_type<uint>(q{read});")

    elif shape == "chain":
        count = case["count"]
        kinds = case.get("producer_kinds", [kind] * count)
        for role in range(count):
            lines.append(
                f"float p{role} = {producer_expr(kinds[role], role)};")
        for role in range(count):
            factor = 16 >> min(role, 3)
            lines.append(f"float q{role} = p{role} * {factor}.0f;")
        for role in range(count):
            lines.append(
                f"out[idx + {role * DISPATCH}u] = as_type<uint>(q{role});")

    elif shape == "gap":
        count = case["initial_count"]
        free_role = case["free_role"]
        for role in range(count):
            lines.append(f"float p{role} = {producer_expr(kind, role)};")
        lines.append(f"float cut = p{free_role} * 16.0f;")
        lines.append("uint dependency = (as_type<uint>(cut) >> 23u) & 1u;")
        lines.append(
            f"float p{count} = {producer_expr(kind, count, 'dependency')};")
        remaining = [role for role in range(count) if role != free_role]
        for ordinal, role in enumerate(remaining + [count]):
            factor = 8 >> min(ordinal, 2)
            lines.append(f"float q{role} = p{role} * {factor}.0f;")
        lines.append("out[idx] = as_type<uint>(cut);")
        for ordinal, role in enumerate(remaining + [count], 1):
            lines.append(
                f"out[idx + {ordinal * DISPATCH}u] = as_type<uint>(q{role});")

    elif shape == "sequential_retain":
        lines.append(f"float p0 = {producer_expr(kind, 0)};")
        lines.append("float first = p0 * 16.0f;")
        lines.append("uint dependency = (as_type<uint>(first) >> 23u) & 1u;")
        lines.append(f"float p1 = {producer_expr(kind, 1, 'dependency')};")
        lines.append("float second = p1 * 8.0f;")
        lines.append("float later = p0 * 4.0f;")
        lines.append("out[idx] = as_type<uint>(first);")
        lines.append(f"out[idx + {DISPATCH}u] = as_type<uint>(second);")
        lines.append(f"out[idx + {2 * DISPATCH}u] = as_type<uint>(later);")

    elif shape == "binary_gap":
        free_role = case["free_role"]
        for role in range(3):
            lines.append(f"float p{role} = {producer_expr('load', role)};")
        lines.append(f"float cut = p{free_role} * 16.0f;")
        remaining = [role for role in range(3) if role != free_role]
        lines.append(f"float result = p{remaining[0]} + p{remaining[1]};")
        lines.append("out[idx] = as_type<uint>(result);")
        lines.append(f"out[idx + {DISPATCH}u] = as_type<uint>(cut);")

    elif shape == "gap_walk":
        for role in range(3):
            lines.append(f"float p{role} = {producer_expr('load', role)};")
        lines.append("float cut0 = p0 * 16.0f;")
        lines.append("uint dep0 = (as_type<uint>(cut0) >> 23u) & 1u;")
        lines.append(f"float n0 = {producer_expr('load', 3, 'dep0')};")
        lines.append("float cut1 = p1 * 8.0f;")
        lines.append("uint dep1 = (as_type<uint>(cut1) >> 22u) & 1u;")
        lines.append(
            f"float n1 = {producer_expr('load', 4, 'dep0 + dep1')};")
        lines.append("float pair = n0 + n1;")
        lines.append("float tail = p2 * 4.0f;")
        lines.append("out[idx] = as_type<uint>(cut0);")
        lines.append(f"out[idx + {DISPATCH}u] = as_type<uint>(cut1);")
        lines.append(f"out[idx + {2 * DISPATCH}u] = as_type<uint>(pair);")
        lines.append(f"out[idx + {3 * DISPATCH}u] = as_type<uint>(tail);")

    elif shape == "gap_refill":
        producer_kind = case.get("kind", "load")
        free_role = case["free_role"]
        for role in range(3):
            lines.append(
                f"float p{role} = {producer_expr(producer_kind, role)};")
        remaining = [role for role in range(3) if role != free_role]
        lines.append(f"float cut = p{free_role} * 16.0f;")
        lines.append("uint dep0 = (as_type<uint>(cut) >> 23u) & 1u;")
        lines.append(
            f"float n0 = {producer_expr(producer_kind, 3, 'dep0')};")
        lines.append(f"float mid = p{remaining[0]} * 8.0f;")
        lines.append("uint dep1 = (as_type<uint>(mid) >> 22u) & 1u;")
        lines.append(
            f"float n1 = {producer_expr(producer_kind, 4, 'dep0 + dep1')};")
        lines.append(f"float tail = p{remaining[1]} * 4.0f;")
        lines.append("float pair = n0 + n1;")
        lines.append("out[idx] = as_type<uint>(cut);")
        lines.append(f"out[idx + {DISPATCH}u] = as_type<uint>(mid);")
        lines.append(f"out[idx + {2 * DISPATCH}u] = as_type<uint>(tail);")
        lines.append(f"out[idx + {3 * DISPATCH}u] = as_type<uint>(pair);")

    elif shape == "binary":
        kinds = case["producer_kinds"]
        lines.append(f"float p0 = {producer_expr(kinds[0], 0)};")
        lines.append(f"float p1 = {producer_expr(kinds[1], 1)};")
        if case.get("prior_role") is not None:
            prior = case["prior_role"]
            lines.append(f"float prior = p{prior} * 16.0f;")
        lines.append("float result = p0 + p1;")
        lines.append("out[idx] = as_type<uint>(result);")
        if case.get("prior_role") is not None:
            lines.append(
                f"out[idx + {DISPATCH}u] = as_type<uint>(prior);")

    elif shape == "fma":
        kinds = case["producer_kinds"]
        for role, producer_kind in enumerate(kinds):
            lines.append(f"float p{role} = {producer_expr(producer_kind, role)};")
        lines.append("float result = fma(p0, p1, p2);")
        lines.append("out[idx] = as_type<uint>(result);")

    else:
        raise KeyError(shape)

    body = "\n  ".join(lines)
    volatile = " volatile" if case.get("volatile_pointer") else ""
    return f"""#include <metal_stdlib>
using namespace metal;
kernel void {case['id']}(
    device const{volatile} float *in0 [[buffer(0)]],
    texture2d<float, access::read> texf [[texture(1)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]]) {{
  {body}
}}
"""


def expected(case: dict) -> bytes:
    words = [0xCCCCCCCC] * WORDS
    for lane in range(DISPATCH):
        shape = case["shape"]
        if shape == "fanout":
            p0 = producer_value(case["kind"], lane, 0)
            for read, factor in enumerate((16, 8, 4)):
                words[lane + read * DISPATCH] = fbits(f32(p0 * factor))
        elif shape == "chain":
            kinds = case.get("producer_kinds")
            if kinds is None:
                kinds = [case["kind"]] * case["count"]
            for role in range(case["count"]):
                value = producer_value(kinds[role], lane, role)
                factor = 16 >> min(role, 3)
                words[lane + role * DISPATCH] = fbits(f32(value * factor))
        elif shape == "gap":
            count = case["initial_count"]
            free_role = case["free_role"]
            initial = [producer_value(case["kind"], lane, role)
                       for role in range(count)]
            cut = f32(initial[free_role] * 16.0)
            dependency = (fbits(cut) >> 23) & 1
            if case["kind"] == "load":
                added = load_value((lane + count * 37 + dependency) &
                                   (WORDS - 1))
            else:
                added = texture_value((lane + count * 37 + dependency) & 15)
            values = {role: value for role, value in enumerate(initial)}
            values[count] = added
            words[lane] = fbits(cut)
            remaining = [role for role in range(count) if role != free_role]
            for ordinal, role in enumerate(remaining + [count], 1):
                factor = 8 >> min(ordinal - 1, 2)
                words[lane + ordinal * DISPATCH] = fbits(
                    f32(values[role] * factor))
        elif shape == "sequential_retain":
            p0 = producer_value(case["kind"], lane, 0)
            first = f32(p0 * 16.0)
            dependency = (fbits(first) >> 23) & 1
            if case["kind"] == "load":
                p1 = load_value((lane + 37 + dependency) & (WORDS - 1))
            else:
                p1 = texture_value((lane + 37 + dependency) & 15)
            words[lane] = fbits(first)
            words[lane + DISPATCH] = fbits(f32(p1 * 8.0))
            words[lane + 2 * DISPATCH] = fbits(f32(p0 * 4.0))
        elif shape == "binary_gap":
            values = [producer_value("load", lane, role) for role in range(3)]
            remaining = [role for role in range(3)
                         if role != case["free_role"]]
            words[lane] = fbits(f32(values[remaining[0]] +
                                    values[remaining[1]]))
            words[lane + DISPATCH] = fbits(
                f32(values[case["free_role"]] * 16.0))
        elif shape == "gap_walk":
            p = [producer_value("load", lane, role) for role in range(3)]
            cut0 = f32(p[0] * 16.0)
            dep0 = (fbits(cut0) >> 23) & 1
            n0 = load_value((lane + 3 * 37 + dep0) & (WORDS - 1))
            cut1 = f32(p[1] * 8.0)
            dep1 = (fbits(cut1) >> 22) & 1
            n1 = load_value((lane + 4 * 37 + dep0 + dep1) &
                            (WORDS - 1))
            words[lane] = fbits(cut0)
            words[lane + DISPATCH] = fbits(cut1)
            words[lane + 2 * DISPATCH] = fbits(f32(n0 + n1))
            words[lane + 3 * DISPATCH] = fbits(f32(p[2] * 4.0))
        elif shape == "gap_refill":
            producer_kind = case.get("kind", "load")
            free_role = case["free_role"]
            p = [producer_value(producer_kind, lane, role)
                 for role in range(3)]
            remaining = [role for role in range(3) if role != free_role]
            cut = f32(p[free_role] * 16.0)
            dep0 = (fbits(cut) >> 23) & 1
            if producer_kind == "load":
                n0 = load_value((lane + 3 * 37 + dep0) & (WORDS - 1))
            else:
                n0 = texture_value((lane + 3 * 37 + dep0) & 15)
            mid = f32(p[remaining[0]] * 8.0)
            dep1 = (fbits(mid) >> 22) & 1
            if producer_kind == "load":
                n1 = load_value((lane + 4 * 37 + dep0 + dep1) &
                                (WORDS - 1))
            else:
                n1 = texture_value((lane + 4 * 37 + dep0 + dep1) & 15)
            words[lane] = fbits(cut)
            words[lane + DISPATCH] = fbits(mid)
            words[lane + 2 * DISPATCH] = fbits(
                f32(p[remaining[1]] * 4.0))
            words[lane + 3 * DISPATCH] = fbits(f32(n0 + n1))
        elif shape == "binary":
            kinds = case["producer_kinds"]
            values = [producer_value(kinds[role], lane, role)
                      for role in range(2)]
            words[lane] = fbits(f32(values[0] + values[1]))
            if case.get("prior_role") is not None:
                prior = case["prior_role"]
                words[lane + DISPATCH] = fbits(f32(values[prior] * 16.0))
        elif shape == "fma":
            kinds = case["producer_kinds"]
            values = [producer_value(kinds[role], lane, role)
                      for role in range(3)]
            words[lane] = fbits(math.fma(values[0], values[1], values[2]))
        else:
            raise KeyError(shape)
    return struct.pack(f"<{WORDS}I", *words)


def definitions() -> list[dict]:
    cases: list[dict] = []
    for kind in ("load", "texture"):
        cases.append({"id": f"r34_{kind}_fanout3", "kind": kind,
                      "shape": "fanout"})
        for count in (1, 2, 3, 5):
            cases.append({"id": f"r34_{kind}_chain{count}", "kind": kind,
                          "shape": "chain", "count": count})
        for free_role in range(3):
            cases.append({
                "id": f"r34_{kind}_gap3_free{free_role}",
                "kind": kind,
                "shape": "gap",
                "initial_count": 3,
                "free_role": free_role,
            })
        cases.append({"id": f"r34_{kind}_sequential_retain",
                      "kind": kind, "shape": "sequential_retain"})

    for kinds in (("load", "load", "texture"),
                  ("load", "texture", "load"),
                  ("texture", "load", "load"),
                  ("texture", "texture", "load"),
                  ("texture", "load", "texture"),
                  ("load", "texture", "texture")):
        label = "_".join(kinds)
        cases.append({
            "id": f"r34_mixed_chain_{label}",
            "shape": "chain",
            "count": 3,
            "producer_kinds": list(kinds),
        })

    cases.append({
        "id": "r34_load_gap_walk",
        "shape": "gap_walk",
        "volatile_pointer": True,
    })
    for free_role in range(3):
        cases.append({
            "id": f"r34_load_gap_refill_free{free_role}",
            "shape": "gap_refill",
            "free_role": free_role,
            "volatile_pointer": True,
        })
    cases.append({
        "id": "r34_texture_gap_refill_free2",
        "shape": "gap_refill",
        "kind": "texture",
        "free_role": 2,
    })

    for free_role in range(3):
        cases.append({
            "id": f"r34_load_vgap3_free{free_role}",
            "kind": "load",
            "shape": "gap",
            "initial_count": 3,
            "free_role": free_role,
            "volatile_pointer": True,
        })
        cases.append({
            "id": f"r34_binary_load_gap_free{free_role}",
            "shape": "binary_gap",
            "free_role": free_role,
            "volatile_pointer": True,
        })

    for kinds in (("load", "load"), ("texture", "texture"),
                  ("load", "texture"), ("texture", "load")):
        label = "_".join(kinds)
        cases.append({"id": f"r34_binary_{label}_direct", "shape": "binary",
                      "producer_kinds": list(kinds)})
        for prior in (0, 1):
            cases.append({"id": f"r34_binary_{label}_prior{prior}",
                          "shape": "binary", "producer_kinds": list(kinds),
                          "prior_role": prior})

    for kinds in (("load", "load", "load"),
                  ("texture", "texture", "texture"),
                  ("load", "texture", "load")):
        label = "_".join(kinds)
        cases.append({"id": f"r34_fma_{label}_direct", "shape": "fma",
                      "producer_kinds": list(kinds)})
    return cases


def sha(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    (GENERATED / "sources").mkdir(parents=True)
    (GENERATED / "oracles").mkdir()
    cases = definitions()
    for case in cases:
        source_path = GENERATED / "sources" / f"{case['id']}.metal"
        expected_path = GENERATED / "oracles" / f"{case['id']}.bin"
        source_path.write_text(make_source(case))
        expected_path.write_bytes(expected(case))
        case.update({
            "cell_id": case["id"],
            "stage": "compute",
            "source": str(source_path.relative_to(HERE)),
            "compute_function": case["id"],
            "expected": str(expected_path.relative_to(HERE)),
            "expected_sha256": sha(expected_path),
            "math_mode": "precise",
            "dispatch_threads": DISPATCH,
            "threads_per_threadgroup": DISPATCH,
        })
    cases_path = GENERATED / "cases.json"
    cases_path.write_text(json.dumps({
        "schema_version": 1,
        "scope": "native Metal route allocation, lifetime, and multi-source closure",
        "cases": cases,
    }, indent=2, sort_keys=True) + "\n")
    files = []
    for path in sorted(GENERATED.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files.append({"path": str(path.relative_to(HERE)),
                          "size": path.stat().st_size, "sha256": sha(path)})
    (GENERATED / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "files": files,
    }, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(cases)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
