#!/usr/bin/env python3
"""G16 tests of Mesa's split high-register fields for get_sr/ilogic/isel."""

import importlib.util
import struct
import sys
from pathlib import Path

H = Path("/Users/nsheth/agx-re/experiments/EXP-0236-falu3-register-reach/harness")
sys.path.insert(0, str(H))
spec = importlib.util.spec_from_file_location("run236", H / "run236.py")
R = importlib.util.module_from_spec(spec)
sys.modules["run236"] = R
spec.loader.exec_module(R)
S, P, B = R.S, R.P, R.B
ORIGINAL_BUILD = R.build_program_for

TARGETS = (0, 15, 16, 31, 32, 47, 48, 63, 64, 79, 80, 95)
OBS_RESULT = 1500
OBS_LOW = 1510
OBS_TARGET = 1511
OBS_BANK64 = 1512


def fv(v, note):
    return S.FV(v, S.RULE, "G16 split-register-field audit", note)


def build_cases(include_hazard=False, full=False):
    out = [{"i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
            "kind": "s0_slot", "slot": slot, "expect_match": True,
            "predicted_bucket": "measure", "expect_sentinel": False}
           for slot in range(8)]
    for target in TARGETS:
        out.append({"i": len(out), "name": "logic_dst_r%02d" % target,
                    "arm": "LD", "kind": "logic_dst", "target": target,
                    "expect_match": True, "predicted_bucket": "measure"})
    for role in ("a", "b"):
        for target in TARGETS:
            out.append({"i": len(out), "name": "logic_src%s_r%02d" % (role, target),
                        "arm": "LS", "kind": "logic_src", "role": role,
                        "target": target, "expect_match": True,
                        "predicted_bucket": "measure"})
    for role in ("cmpa", "cmpb", "true", "false"):
        for target in TARGETS:
            out.append({"i": len(out), "name": "isel_%s_r%02d" % (role, target),
                        "arm": "IS", "kind": "isel_src", "role": role,
                        "target": target, "expect_match": True,
                        "predicted_bucket": "measure"})
    for target in TARGETS:
        for observe_role in ("low", "target", "bank64"):
            out.append({"i": len(out),
                        "name": "getsr_dst_r%02d_%s" % (target, observe_role),
                        "arm": "SR", "kind": "getsr_dst", "target": target,
                        "observe_role": observe_role, "expect_match": True,
                        "predicted_bucket": "measure"})
    return out


def store(pg, store_index, reg, out_off, value, tag):
    R.generated_store(pg, store_index, reg, out_off, value, tag)


def observe(pg, store_index, reg, out_off, tag):
    store(pg, store_index, reg, out_off, pg.rbits(reg), tag)


def load_int(pg, load_index, store_index, reg, number, tag):
    value = P.codeword(number)
    previous = pg.rbits(reg)
    S.device_load(pg.E, load_index, P.CODEWORD_BASE + number, 3,
                  pg.slots["imem"], reg, salt=tag + "_load",
                  offnatural=False, ld_format=17, extmode=2 * reg,
                  addr_mode=0x44)
    pg.set_reg(reg, value)
    pg._pending = (reg, previous)
    store(pg, store_index, reg, 1600 + number, value, tag + "_fwd")
    return value


def setup(pg, excluded):
    store_index, load_index = R.choose_indices(set(excluded))
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    return store_index, load_index


def emit_xor(pg, dst, db_a, db_b):
    pg.E.emit("ilogic", {
        "dst": fv(dst, "low destination"),
        "srcA": fv((db_a << 1) | 1, "db source A"),
        "op_base": fv(0, "XOR base"),
        "srcB": fv((db_b << 1) | 1, "db source B"),
        "lut_a_sel": fv(2, "XOR selector"), "lut_a_free": fv(0, "canonical"),
        "lut_a_z": fv(0, "canonical"), "lut_b": fv(8, "XOR selector"),
        "z6": fv(0, "canonical"), "outmod": fv(0x80, "read enable"),
        "z8": fv(0, "canonical"), "z9": fv(0, "canonical"),
    })


def mutate_last(pg, fn):
    off, mnemonic, requested, data = pg.E.parts[-1]
    b = bytearray(data)
    fn(b)
    pg.E.parts[-1] = (off, mnemonic, requested, bytes(b))


def logic_dst_program(case, slots, carrier_len):
    target, low = case["target"], case["target"] & 15
    sources = [r for r in range(2, 11) if r not in (target, low)][:2]
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, low, *sources})
    for reg, number in ((low, 20), (sources[0], 21), (sources[1], 22)):
        load_int(pg, li, si, reg, number, "seed_r%d" % reg)
    if target != low:
        load_int(pg, li, si, target, 23, "seed_target")
    low_before, high_before = pg.rbits(low), pg.rbits(target)
    result = pg.rbits(sources[0]) ^ pg.rbits(sources[1])
    pg.body_start = pg.E.off
    emit_xor(pg, low, sources[0], sources[1])
    mutate_last(pg, lambda b: (b.__setitem__(2, (b[2] & 0x3f) |
                                                 (((target >> 4) & 3) << 6)),
                               b.__setitem__(5, (b[5] & 0xef) |
                                                 (((target >> 6) & 1) << 4))))
    pg.body_end = pg.E.off
    pg.set_reg(sources[0], 0); pg.set_reg(sources[1], 0); pg.set_reg(low, result)
    observe(pg, si, low, OBS_LOW, "post_low")
    observe(pg, si, target, OBS_TARGET, "post_target")
    pg.audit = {"target": target, "low": low, "result": result,
                "low_before": low_before, "high_before": high_before}
    return pg, pg.finish(carrier_len)


def logic_src_program(case, slots, carrier_len):
    target, alias, role = case["target"], case["target"] & 63, case["role"]
    dst = next(r for r in range(2, 11) if r not in (target, alias))
    other = next(r for r in range(2, 11) if r not in (target, alias, dst))
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, alias, dst, other})
    load_int(pg, li, si, alias, 20, "seed_alias")
    if target != alias: load_int(pg, li, si, target, 23, "seed_target")
    load_int(pg, li, si, other, 21, "seed_other")
    db_a, db_b = (alias, other) if role == "a" else (other, alias)
    alias_result = pg.rbits(alias) ^ pg.rbits(other)
    high_result = pg.rbits(target) ^ pg.rbits(other)
    pg.body_start = pg.E.off
    emit_xor(pg, dst, db_a, db_b)
    if target >= 64:
        mutate_last(pg, lambda b: b.__setitem__(5, b[5] | (0x01 if role == "a" else 0x04)))
    pg.body_end = pg.E.off
    pg.set_reg(db_a, 0); pg.set_reg(db_b, 0); pg.set_reg(dst, alias_result)
    observe(pg, si, dst, OBS_RESULT, "post_result")
    pg.audit = {"target": target, "alias": alias, "role": role,
                "alias_result": alias_result, "high_result": high_result}
    return pg, pg.finish(carrier_len)


def emit_isel(pg, dst, cmpa, cmpb, true_reg, false_reg):
    pg.E.emit("isel10", {
        "dst": fv(dst, "low destination"),
        "cmpA": fv((cmpa << 1) | 1, "compare A"), "opsel": fv(0, "retain"),
        "cmpB": fv((cmpb << 1) | 1, "compare B"),
        "cmp_mode": fv(0x06, "integer equality"),
        "selTrue": fv(true_reg << 1, "true source"), "cc": fv(7, "equality"),
        "flags": fv(0xc0, "dependency flags"),
        "selFalse_file": fv(0, "GPR false"),
        "selFalse": fv(false_reg << 1, "false source"),
    })


def isel_src_program(case, slots, carrier_len):
    target, alias, role = case["target"], case["target"] & 63, case["role"]
    free = [r for r in range(2, 12) if r not in (target, alias)]
    dst, q0, q1, q2 = free[:4]
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, alias, dst, q0, q1, q2})
    load_int(pg, li, si, alias, 20, "seed_alias")
    if target != alias: load_int(pg, li, si, target, 23, "seed_target")
    # Build two independent candidate outcomes for the selected role.
    if role == "cmpa":
        cmpa, cmpb, tr, fl = alias, q0, q1, q2
        load_int(pg, li, si, q0, 23 if target != alias else 20, "cmp_partner")
        load_int(pg, li, si, q1, 21, "true"); load_int(pg, li, si, q2, 22, "false")
    elif role == "cmpb":
        cmpa, cmpb, tr, fl = q0, alias, q1, q2
        load_int(pg, li, si, q0, 23 if target != alias else 20, "cmp_partner")
        load_int(pg, li, si, q1, 21, "true"); load_int(pg, li, si, q2, 22, "false")
    elif role == "true":
        cmpa, cmpb, tr, fl = q0, q1, alias, q2
        load_int(pg, li, si, q0, 21, "cmpa"); load_int(pg, li, si, q1, 21, "cmpb")
        load_int(pg, li, si, q2, 22, "false")
    else:
        cmpa, cmpb, tr, fl = q0, q1, q2, alias
        load_int(pg, li, si, q0, 21, "cmpa"); load_int(pg, li, si, q1, 22, "cmpb")
        load_int(pg, li, si, q2, 21, "true")
    def result(using_high):
        av = pg.rbits(target if using_high and role == "cmpa" else cmpa)
        bv = pg.rbits(target if using_high and role == "cmpb" else cmpb)
        tv = pg.rbits(target if using_high and role == "true" else tr)
        fval = pg.rbits(target if using_high and role == "false" else fl)
        return tv if av == bv else fval
    alias_result, high_result = result(False), result(True)
    pg.body_start = pg.E.off
    emit_isel(pg, dst, cmpa, cmpb, tr, fl)
    if target >= 64:
        def ext(b):
            if role == "cmpa": b[7] |= 0x01
            elif role == "cmpb": b[7] |= 0x04
            elif role == "true": b[4] |= 0x40
            else: b[8] |= 0x40
        mutate_last(pg, ext)
    pg.body_end = pg.E.off
    pg.set_reg(dst, alias_result)
    observe(pg, si, dst, OBS_RESULT, "post_result")
    pg.audit = {"target": target, "alias": alias, "role": role,
                "alias_result": alias_result, "high_result": high_result}
    return pg, pg.finish(carrier_len)


def getsr_program(case, slots, carrier_len):
    target, low = case["target"], case["target"] & 15
    bank64 = 64 + low
    candidates = {"low": low, "target": target, "bank64": bank64}
    role = case["observe_role"]
    observe_reg = candidates[role]
    free = [r for r in range(2, 12) if r not in (target, low, bank64)]
    dst, partner = free[:2]
    pg = P.Prog(slots, case["name"], offnatural=False)
    si, li = setup(pg, {target, low, bank64, dst, partner})
    seeds = {low: 20, target: 21, bank64: 22}
    for reg, number in seeds.items(): load_int(pg, li, si, reg, number, "seed_r%d" % reg)
    partner_value = load_int(pg, li, si, partner, 23, "seed_partner")
    before = {r: pg.rbits(r) for r in seeds}
    pg.body_start = pg.E.off
    pg.E.emit("get_sr", {
        "form": fv(0, "32-bit form"), "dst": fv(low, "low destination"),
        "sr_sel": fv(152, "threads_per_threadgroup.x"),
        "dp_width": fv(0x50 if target >= 64 else 0x10, "Mesa bank selection"),
        "dp_marker": fv(6, "32-bit marker"),
        "dst_hi": fv((target >> 4) & 7, "Mesa alleged destination high bits"),
    })
    # Materialize the candidate through a now-validated general integer-logic
    # source. This avoids asking a memory store to consume the get_sr result
    # directly, which has a distinct publication path.
    emit_xor(pg, dst, observe_reg & 63, partner)
    if observe_reg >= 64:
        mutate_last(pg, lambda b: b.__setitem__(5, b[5] | 0x01))
    pg.body_end = pg.E.off
    seed_result = before[observe_reg] ^ partner_value
    sr_result = 1 ^ partner_value
    zero_result = partner_value
    pg.set_reg(observe_reg, 0); pg.set_reg(partner, 0); pg.set_reg(dst, seed_result)
    observe(pg, si, dst, OBS_RESULT, "post_" + role)
    pg.audit = {"target": target, "low": low, "bank64": bank64,
                "observe_role": role, "observe_reg": observe_reg,
                "before": before, "seed_result": seed_result,
                "sr_result": sr_result, "zero_result": zero_result}
    return pg, pg.finish(carrier_len)


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0": return ORIGINAL_BUILD(case, slots, carrier_len)
    return {"logic_dst": logic_dst_program, "logic_src": logic_src_program,
            "isel_src": isel_src_program, "getsr_dst": getsr_program}[case["kind"]](
                case, slots, carrier_len)


def word(res, slots, off):
    return R.read_word(res, slots["out"], off)


def score_audit(case, pg, prog, rows, bad, alias, res, base_state, oracle,
                slots, dispatched_ok):
    rec = R.BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                       oracle, slots, dispatched_ok)
    if case["kind"] == "logic_dst":
        o = {"low": word(res, slots, OBS_LOW), "target": word(res, slots, OBS_TARGET)}
        e = pg.audit
        model = ("extended_high" if e["target"] != e["low"] and
                 o["target"] == e["result"] and o["low"] == e["low_before"] else
                 "canonical_low" if o["low"] == e["result"] else "other_or_corrupt")
        rec["audit_probe"] = {"model": model, "observed": o, "expected": e}
    elif case["kind"] in ("logic_src", "isel_src"):
        got, e = word(res, slots, OBS_RESULT), pg.audit
        model = ("extended_high" if got == e["high_result"] else
                 "canonical_alias" if got == e["alias_result"] else "other_or_corrupt")
        rec["audit_probe"] = {"model": model, "observed": got, "expected": e}
    elif case["kind"] == "getsr_dst":
        e = pg.audit
        got = word(res, slots, OBS_RESULT)
        model = ("system_value" if got == e["sr_result"] else
                 "seed_unchanged" if got == e["seed_result"] else
                 "zero_or_invalid" if got == e["zero_result"] else
                 "other_or_corrupt")
        rec["audit_probe"] = {"model": model, "observed": got, "expected": e}
    return rec


R.build_cases = build_cases
R.build_program_for = build_program_for
B.C = R
B.score = score_audit
raise SystemExit(B.main())
