#!/usr/bin/env python3
"""Generate whole-program probes for direct pending-load device stores.

The programs are independently assembled from the public Apple9 instruction
database.  They use two distinct input words, destination GPRs, producer
scoreboard tags, and output addresses so a single execution identifies both
values consumed by the two direct stores.
"""

from __future__ import annotations

import json
import pathlib
import sys


HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "experiments" / "EXP-0141-m4-emit-mem"))
import isa_helpers as H  # noqa: E402


CARRIER_LEN = 170
R_A = 0
R_B = 1
R_INDEX0 = 15
R_INDEX1 = 14
R_CANARY_INDEX = 13
R_CANARY_VALUE = 12
SLOT_OUT = 0
SLOT_MEM = 1

# Input offsets are 4-byte units for this scalar load form.  Keep word zero as
# a guard and make the two observed values visibly different.
VALUE_A = 0x11111111
VALUE_B = 0x22222222
CANARY = 0x5A
INITIAL = -559038737  # 0xdeadbeef as signed int32 for agxtest.py


def producer_tag(slot: int) -> tuple[int, int]:
    """Return (dst_lo, dst_ext9) for the proven scalar-load slot token."""
    if not 1 <= slot <= 6:
        raise ValueError(slot)
    t = (2 * (slot - 1)) % 7
    return t >> 1, t & 1


def load(value: str, reg: int, slot: int) -> bytes:
    offset = {"A": 1, "B": 2}[value]
    dst_lo, dst_ext9 = producer_tag(slot)
    return H.device_load(
        index_reg=R_INDEX0,
        base_slot=SLOT_MEM,
        extmode=2 * reg,
        dst_lo=dst_lo,
        dst_ext9=dst_ext9,
        idx_off=offset,
    )


def store(index_reg: int, reg: int) -> bytes:
    return H.device_store(
        index_reg=index_reg,
        base_slot=SLOT_OUT,
        data_reg=reg,
        addr_mode=0x56,
    )


def two_load_program(
    issue: tuple[tuple[str, int, int], tuple[str, int, int]],
    store_regs: tuple[int, int],
) -> bytes:
    body = [
        H.mov_imm(R_INDEX0, 0),
        H.mov_imm(R_INDEX1, 1),
        H.mov_imm(R_CANARY_INDEX, 4),
        H.mov_imm(R_CANARY_VALUE, CANARY),
        H.device_store(
            index_reg=R_CANARY_INDEX,
            base_slot=SLOT_OUT,
            data_reg=R_CANARY_VALUE,
            addr_mode=0x54,
        ),
    ]
    body += [load(value, reg, slot) for value, reg, slot in issue]
    body += [store(R_INDEX0, store_regs[0]), store(R_INDEX1, store_regs[1])]
    return H.build_program(body, CARRIER_LEN)


def single_load_program(reg: int, slot: int) -> bytes:
    body = [
        H.mov_imm(R_INDEX0, 0),
        H.mov_imm(R_CANARY_INDEX, 4),
        H.mov_imm(R_CANARY_VALUE, CANARY),
        H.device_store(
            index_reg=R_CANARY_INDEX,
            base_slot=SLOT_OUT,
            data_reg=R_CANARY_VALUE,
            addr_mode=0x54,
        ),
        load("A", reg, slot),
        store(R_INDEX0, reg),
    ]
    return H.build_program(body, CARRIER_LEN)


def case(case_id: str, program: bytes, predicted: list[int], **metadata) -> dict:
    H.assert_round_trip(program)
    return {
        "id": case_id,
        "program": program.hex(),
        "program_length": len(program),
        "predicted_associative_output": predicted,
        **metadata,
    }


def main() -> int:
    cases = []

    # Known-good shape plus producer-token mutations in isolation.  These run
    # first, before any two-pending-result arm.
    for slot in (6, 1, 2):
        for reg in (R_A, R_B):
            cases.append(case(
                f"single_A_slot{slot}_r{reg}",
                single_load_program(reg, slot),
                [VALUE_A],
                kind="single",
                producer_slot=slot,
                producer_reg=reg,
                expected="exact" if slot == 6 else "observe",
            ))

    schedules = [
        (
            "native_A6_B1",
            (("A", R_A, 6), ("B", R_B, 1)),
            "native allocator order: A in slot 6, then B in slot 1",
        ),
        (
            "reverse_B6_A1",
            (("B", R_B, 6), ("A", R_A, 1)),
            "reverse issue/value order while preserving allocator order",
        ),
        (
            "tokenswap_A1_B6",
            (("A", R_A, 1), ("B", R_B, 6)),
            "same issue order with the producer tokens independently swapped",
        ),
        (
            "gap_A6_B2",
            (("A", R_A, 6), ("B", R_B, 2)),
            "leave slot 1 free and publish the second result through slot 2",
        ),
    ]
    for name, issue, note in schedules:
        value_by_reg = {reg: VALUE_A if value == "A" else VALUE_B
                        for value, reg, _slot in issue}
        for store_regs in ((R_A, R_B), (R_B, R_A)):
            predicted = [value_by_reg[store_regs[0]], value_by_reg[store_regs[1]]]
            cases.append(case(
                f"{name}_store_r{store_regs[0]}_r{store_regs[1]}",
                two_load_program(issue, store_regs),
                predicted,
                kind="two_pending",
                issue=[{"value": value, "reg": reg, "slot": slot}
                       for value, reg, slot in issue],
                store_regs=list(store_regs),
                note=note,
                expected="observe",
            ))

    generated = HERE / "generated"
    generated.mkdir(exist_ok=True)
    payload = {
        "schema_version": 1,
        "carrier_length": CARRIER_LEN,
        "inputs": [0, VALUE_A, VALUE_B, 0],
        "initial_output": [INITIAL] * 5,
        "canary_index": 4,
        "canary_value": CANARY,
        "cases": cases,
    }
    (generated / "cases.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"generated {len(cases)} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
