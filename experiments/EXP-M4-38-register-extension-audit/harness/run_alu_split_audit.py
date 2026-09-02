#!/usr/bin/env python3
"""Coupled split-register probes for compact two-source Apple9 ALUs.

The older descriptor sweeps varied bits 15/31 while leaving the register-bank
bits in byte 5 clear.  This runner instead seeds R and R+64 differently and
changes the complete proposed encoding together:

    dst[5:4] = bits 23:22, dst[6] = bit 44
    srcA[6]  = bit 40,    srcB[6] = bit 42

FALU2, integer min/max, and native half ALU all have the same six-byte operand
skeleton.  Every probe observes complete values through independently proven
device stores; merely retiring the command buffer is not a positive result.
"""

import importlib.util
import struct
import sys
from pathlib import Path


H = Path("/Users/nsheth/agx-re/experiments/EXP-0236-falu3-register-reach/harness")
if not H.exists():
    H = (Path(__file__).resolve().parents[2] /
         "EXP-0236-falu3-register-reach" / "harness")
sys.path.insert(0, str(H))
spec = importlib.util.spec_from_file_location("run236", H / "run236.py")
R = importlib.util.module_from_spec(spec)
sys.modules["run236"] = R
spec.loader.exec_module(R)

S, P, B = R.S, R.P, R.B
ORIGINAL_BUILD = R.build_program_for

DST_TARGETS = (0, 16, 32, 48, 64, 80, 95)
SRC_TARGETS = (0, 15, 16, 31, 32, 47, 48, 63, 64, 79, 80, 95)

OBS_PRE_LOW = 1700
OBS_PRE_TARGET = 1701
OBS_POST_LOW = 1710
OBS_POST_TARGET = 1711
OBS_RESULT = 1720
OBS_ALIAS = 1721


def fv(value, note):
    return S.FV(value, S.RULE, "EXP-M4-38 coupled split-register audit", note)


def mutate_last(pg, fn):
    off, mnemonic, requested, data = pg.E.parts[-1]
    b = bytearray(data)
    fn(b)
    pg.E.parts[-1] = (off, mnemonic, requested, bytes(b))


def apply_destination_extension(b, target):
    b[2] = (b[2] & 0x3f) | (((target >> 4) & 3) << 6)
    b[5] = (b[5] & 0xef) | (((target >> 6) & 1) << 4)


def apply_source_extension(b, role, target):
    if target >= 64:
        b[5] |= 0x01 if role == "a" else 0x04


def setup(pg, excluded):
    store_index, load_index = R.choose_indices(set(excluded))
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    return store_index, load_index


def observe(pg, store_index, reg, out_off, tag):
    R.generated_store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def load_int(pg, load_index, store_index, reg, word, tag):
    value = P.IMEM[word]
    previous = pg.rbits(reg)
    S.device_load(pg.E, load_index, word, 3, pg.slots["imem"], reg,
                  salt=tag + "_load", offnatural=False, ld_format=17,
                  extmode=2 * reg, addr_mode=0x44)
    pg.set_reg(reg, value)
    pg._pending = (reg, previous)
    R.generated_store(pg, store_index, reg, 1450 + word, value,
                      tag + "_materialize", addr_mode=S.DS_ADDRMODE_LOADFWD)
    return value


def load_float(pg, load_index, store_index, reg, word, tag):
    return R.generated_load_float(pg, load_index, store_index, reg, word,
                                  1400 + (word & 31), tag)


def emit_falu2(pg, dst, a, b):
    pg.E.emit("falu2", {
        "dst": fv(dst & 15, "destination low nibble"),
        "srcA_size": fv(1, "FP32 source A"),
        "srcA_reg": fv(a & 63, "source-A low six register bits"),
        "srcA_aux": fv(0, "canonical descriptor auxiliary"),
        "opsel": fv(4, "float add"),
        "opflags": fv(3, "canonical source release state"),
        "dst_mid": fv(0, "destination bits 4..5"),
        "srcB_size": fv(1, "FP32 source B"),
        "srcB_reg": fv(b & 63, "source-B low six register bits"),
        "srcB_aux": fv(0, "canonical descriptor auxiliary"),
        "ctrl": fv(0, "six-byte form"),
        "srcB_imm": fv(0, "GPR source B"),
        "srcA_hi": fv(0, "source-A register bit 6"),
        "srcB_file": fv(0, "source-B GPR file"),
        "srcB_hi": fv(0, "source-B register bit 6"),
        "srcB_neg": fv(0, "positive source B"),
        "dst_hi": fv(0, "destination register bit 6"),
        "scoreboard_slot": fv(6, "canonical pending-result slot"),
    })


def emit_imin(pg, dst, a, b):
    # Canonical compiler-produced unsigned-min skeleton.  The register
    # descriptors occupy the same byte-1/byte-3 positions as FALU2.
    pg.E.emit("iminmax", {
        "dst": fv(dst & 15, "compact destination nibble"),
        "srcA_size": fv(1, "32-bit source A"),
        "srcA_reg": fv(a & 63, "source-A low six register bits"),
        "srcA_aux": fv(0, "canonical descriptor auxiliary"),
        "fmt": fv(3, "canonical two-source release/publish state"),
        "dst_mid": fv(0, "destination bits 4..5"),
        "srcB_size": fv(1, "32-bit source B"),
        "srcB_reg": fv(b & 63, "source-B low six register bits"),
        "srcB_aux": fv(0, "canonical descriptor auxiliary"),
        "sel": fv(5, "unsigned minimum"),
        "selhi": fv(0, "canonical selector high bits"),
        "srcA_hi": fv(0, "source-A register bit 6"),
        "srcB_file": fv(0, "source-B GPR mode"),
        "srcB_hi": fv(0, "source-B register bit 6"),
        "src_modifier": fv(0, "canonical source modifier"),
        "dst_hi": fv(0, "destination register bit 6"),
        "scoreboard_slot": fv(0, "canonical no-pending slot"),
    })


def emit_falu2_ext(pg, dst, a, b):
    # Eight-byte saturating FADD.  The first six bytes retain FALU2's operand
    # skeleton; ctrl=1 selects the extended tail and 0x8200 enables saturate.
    pg.E.emit("falu2_ext", {
        "dst": fv(dst & 15, "compact destination nibble"),
        "srcA_size": fv(1, "FP32 source A"),
        "srcA_reg": fv(a & 63, "source-A low six register bits"),
        "srcA_aux": fv(0, "canonical descriptor auxiliary"),
        "opsel": fv(4, "float add"),
        "opflags": fv(3, "canonical source release state"),
        "dst_mid": fv(0, "destination bits 4..5"),
        "srcB_size": fv(1, "FP32 source B"),
        "srcB_reg": fv(b & 63, "source-B low six register bits"),
        "srcB_aux": fv(0, "canonical descriptor auxiliary"),
        "ctrl": fv(1, "eight-byte form"),
        "srcB_imm": fv(0, "GPR source B"),
        "srcA_hi": fv(0, "source-A register bit 6"),
        "srcB_file": fv(0, "source-B GPR file"),
        "srcB_hi": fv(0, "source-B register bit 6"),
        "srcB_neg": fv(0, "positive source B"),
        "dst_hi": fv(0, "destination register bit 6"),
        "scoreboard_slot": fv(0, "canonical no-pending slot"),
        "ext_tail": fv(0x8200, "saturate tail"),
    })


def emit_falu2_srcmod10(pg, dst, a, b):
    # Ten-byte source-modifier form with no abs/negate modifiers enabled.
    pg.E.emit("falu2_srcmod10", {
        "dst": fv(dst & 15, "compact destination nibble"),
        "srcA_size": fv(1, "FP32 source A"),
        "srcA_reg": fv(a & 63, "source-A low six register bits"),
        "srcA_aux": fv(0, "canonical descriptor auxiliary"),
        "opsel": fv(4, "float add"),
        "opflags": fv(3, "canonical source release state"),
        "dst_mid": fv(0, "destination bits 4..5"),
        "srcB_size": fv(1, "FP32 source B"),
        "srcB_reg": fv(b & 63, "source-B low six register bits"),
        "srcB_aux": fv(0, "canonical descriptor auxiliary"),
        "ctrl": fv(2, "ten-byte form"),
        "srcB_imm": fv(0, "GPR source B"),
        "srcA_hi": fv(0, "source-A register bit 6"),
        "srcB_file": fv(0, "source-B GPR file"),
        "srcB_hi": fv(0, "source-B register bit 6"),
        "srcB_neg": fv(0, "positive source B"),
        "dst_hi": fv(0, "destination register bit 6"),
        "scoreboard_slot": fv(0, "canonical no-pending slot"),
        "ext_srcmod": fv(0x00008000, "valid tail with no source modifiers"),
    })


def emit_half_add(pg, dst, a, b):
    # Low-half scalar add.  The high 16 bits of the destination are preserved.
    pg.E.emit("half_alu", {
        "dst": fv(dst & 15, "compact destination nibble"),
        "srcA_half": fv(0, "source-A low half"),
        "srcA_reg": fv(a & 63, "source-A low six register bits"),
        "srcA_aux": fv(0, "canonical descriptor auxiliary"),
        "opsel": fv(4, "half add"),
        "opflags": fv(3, "canonical source release state"),
        "dst_mid": fv(0, "destination bits 4..5"),
        "srcB_half": fv(0, "source-B low half"),
        "srcB_reg": fv(b & 63, "source-B low six register bits"),
        "srcB_aux": fv(0, "canonical descriptor auxiliary"),
        "ctrl": fv(0, "six-byte compact form"),
        "srcA_hi": fv(0, "source-A register bit 6"),
        "srcB_file": fv(0, "source-B GPR mode"),
        "srcB_hi": fv(0, "source-B register bit 6"),
        "srcA_neg": fv(0, "positive source A"),
        "dst_hi": fv(0, "destination register bit 6"),
        "scoreboard_slot": fv(6, "canonical compact-half control"),
    })


def half_add_bits(a_bits, b_bits, dst_before):
    a = struct.unpack("<e", struct.pack("<I", a_bits)[:2])[0]
    b = struct.unpack("<e", struct.pack("<I", b_bits)[:2])[0]
    low = struct.unpack("<H", struct.pack("<e", a + b))[0]
    return (dst_before & 0xffff0000) | low


OPS = {
    "falu2": {
        "emit": emit_falu2,
        "seed": "float",
        "alias_word": 19,       # 5.0
        "target_word": 67,      # 17.0
        "other_word": 11,       # 3.0
        "dst_low_word": 39,
        "dst_target_word": 43,
    },
    "falu2_ext": {
        "emit": emit_falu2_ext,
        "seed": "float",
        "alias_word": 0,        # 0.25
        "target_word": 1,       # 0.50
        "other_word": 0,        # 0.25; sums distinguish 0.50 from 0.75
        "dst_low_word": 3,
        "dst_target_word": 4,
    },
    "falu2_srcmod10": {
        "emit": emit_falu2_srcmod10,
        "seed": "float",
        "alias_word": 19,
        "target_word": 67,
        "other_word": 11,
        "dst_low_word": 39,
        "dst_target_word": 43,
    },
    "imin": {
        "emit": emit_imin,
        "seed": "int",
        "alias_word": 10,
        "target_word": 30,
        "other_word": 20,
        "dst_low_word": 40,
        "dst_target_word": 50,
    },
    "half": {
        "emit": emit_half_add,
        "seed": "half",
        "alias_word": 528,      # low half 1.5
        "target_word": 529,     # low half 2.5
        "other_word": 530,      # low half 0.5
        "dst_low_word": 531,
        "dst_target_word": 532,
    },
}


def load_for(pg, si, li, reg, word, kind, tag):
    if kind == "int":
        return load_int(pg, li, si, reg, word, tag)
    return load_float(pg, li, si, reg, word, tag)


def result_for(op, a, b, dst_before):
    if op in ("falu2", "falu2_srcmod10"):
        return P.fbits(S.f32(S.bits_f32(a) + S.bits_f32(b)))
    if op == "falu2_ext":
        value = max(0.0, min(1.0, S.bits_f32(a) + S.bits_f32(b)))
        return P.fbits(S.f32(value))
    if op == "imin":
        return min(a, b)
    return half_add_bits(a, b, dst_before)


def destination_program(case, slots, carrier_len):
    op, target = case["op"], case["target"]
    cfg = OPS[op]
    low = target & 15
    sources = [r for r in range(2, 12) if r not in (target, low)][:2]
    a, b = sources
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, low, a, b})
    load_for(pg, si, li, low, cfg["dst_low_word"], cfg["seed"], "seed_low")
    if target != low:
        load_for(pg, si, li, target, cfg["dst_target_word"], cfg["seed"],
                 "seed_target")
    load_for(pg, si, li, a, cfg["alias_word"], cfg["seed"], "seed_a")
    load_for(pg, si, li, b, cfg["other_word"], cfg["seed"], "seed_b")
    low_before, target_before = pg.rbits(low), pg.rbits(target)
    result = result_for(op, pg.rbits(a), pg.rbits(b), target_before)
    observe(pg, si, low, OBS_PRE_LOW, "pre_low")
    observe(pg, si, target, OBS_PRE_TARGET, "pre_target")

    pg.body_start = pg.E.off
    cfg["emit"](pg, low, a, b)
    mutate_last(pg, lambda raw: apply_destination_extension(raw, target))
    pg.body_end = pg.E.off

    # These compact forms use the canonical last-use state for both sources.
    pg.set_reg(a, 0)
    pg.set_reg(b, 0)
    if target == low:
        pg.set_reg(low, result)
    else:
        pg.set_reg(target, result)
    observe(pg, si, low, OBS_POST_LOW, "post_low")
    observe(pg, si, target, OBS_POST_TARGET, "post_target")
    pg.audit = {"op": op, "target": target, "low": low, "result": result,
                "low_before": low_before, "target_before": target_before}
    return pg, pg.finish(carrier_len)


def source_program(case, slots, carrier_len):
    op, target, role = case["op"], case["target"], case["role"]
    cfg = OPS[op]
    alias = target & 63
    free = [r for r in range(2, 12) if r not in (target, alias)]
    dst, other = free[:2]
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, alias, dst, other})
    load_for(pg, si, li, alias, cfg["alias_word"], cfg["seed"], "seed_alias")
    if target != alias:
        load_for(pg, si, li, target, cfg["target_word"], cfg["seed"],
                 "seed_target")
    load_for(pg, si, li, other, cfg["other_word"], cfg["seed"], "seed_other")
    load_for(pg, si, li, dst, cfg["dst_low_word"], cfg["seed"], "seed_dst")
    dst_before = pg.rbits(dst)
    a, b = (alias, other) if role == "a" else (other, alias)
    alias_result = result_for(op, pg.rbits(a), pg.rbits(b), dst_before)
    high_a = target if role == "a" else other
    high_b = other if role == "a" else target
    high_result = result_for(op, pg.rbits(high_a), pg.rbits(high_b), dst_before)

    pg.body_start = pg.E.off
    cfg["emit"](pg, dst, a, b)
    mutate_last(pg, lambda raw: apply_source_extension(raw, role, target))
    pg.body_end = pg.E.off

    pg.set_reg(dst, high_result if target >= 64 else alias_result)
    pg.set_reg(other, 0)
    if target < 64:
        # Native half ALU releases only the selected 16-bit half.  The
        # following observer store sees the untouched high half, then releases
        # the remaining value before the final register dump.
        if op == "half":
            pg.set_reg(target, pg.rbits(target) & 0xffff0000)
        else:
            pg.set_reg(target, 0)
    else:
        # Correct high-bank consumption must not release the modulo-64 alias.
        pg.set_reg(target, 0)
    observe(pg, si, dst, OBS_RESULT, "post_result")
    observe(pg, si, alias, OBS_ALIAS, "post_alias")
    if op == "half" and target < 64:
        pg.set_reg(alias, 0)
    pg.audit = {"op": op, "target": target, "alias": alias, "role": role,
                "alias_result": alias_result, "high_result": high_result}
    return pg, pg.finish(carrier_len)


def build_cases(include_hazard=False, full=False):
    out = [{"i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
            "kind": "s0_slot", "slot": slot, "expect_match": True,
            "predicted_bucket": "measure", "expect_sentinel": False}
           for slot in range(8)]
    for op, arm in (("falu2", "F2"), ("falu2_ext", "F2E"),
                    ("falu2_srcmod10", "F2M"), ("imin", "IM"),
                    ("half", "H")):
        for target in DST_TARGETS:
            out.append({"i": len(out), "name": "%s_dst_r%02d" % (op, target),
                        "arm": arm + "D", "kind": "alu_dst", "op": op,
                        "target": target, "expect_match": True,
                        "predicted_bucket": "measure"})
        for role in ("a", "b"):
            for target in SRC_TARGETS:
                out.append({"i": len(out),
                            "name": "%s_src%s_r%02d" % (op, role, target),
                            "arm": arm + "S", "kind": "alu_src", "op": op,
                            "role": role, "target": target,
                            "expect_match": True, "predicted_bucket": "measure"})
    return out


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIGINAL_BUILD(case, slots, carrier_len)
    if case["kind"] == "alu_dst":
        return destination_program(case, slots, carrier_len)
    return source_program(case, slots, carrier_len)


def read_word(res, slots, off):
    return R.read_word(res, slots["out"], off)


def score_alu(case, pg, prog, rows, bad, alias, res, base_state, oracle,
              slots, dispatched_ok):
    rec = R.BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                       oracle, slots, dispatched_ok)
    if case["kind"] == "alu_dst":
        e = pg.audit
        observed = {"low": read_word(res, slots, OBS_POST_LOW),
                    "target": read_word(res, slots, OBS_POST_TARGET)}
        if e["target"] == e["low"] and observed["low"] == e["result"]:
            model = "low_control"
        elif (observed["target"] == e["result"] and
              observed["low"] == e["low_before"]):
            model = "extended_high"
        elif observed["low"] == e["result"]:
            model = "canonical_low"
        else:
            model = "other_or_corrupt"
        rec["alu_split_probe"] = {"model": model, "observed": observed,
                                  "expected": e}
    elif case["kind"] == "alu_src":
        e = pg.audit
        got = read_word(res, slots, OBS_RESULT)
        if e["target"] < 64 and got == e["alias_result"]:
            model = "low_control"
        elif got == e["high_result"] and e["high_result"] != e["alias_result"]:
            model = "extended_high"
        elif got == e["alias_result"]:
            model = "canonical_alias"
        else:
            model = "other_or_corrupt"
        rec["alu_split_probe"] = {"model": model, "observed": got,
                                  "expected": e,
                                  "post_alias": read_word(res, slots, OBS_ALIAS)}
    return rec


R.build_cases = build_cases
R.build_program_for = build_program_for
B.C = R
B.score = score_alu
raise SystemExit(B.main())
