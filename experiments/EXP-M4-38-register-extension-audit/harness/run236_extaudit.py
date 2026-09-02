#!/usr/bin/env python3
"""Targeted G16 audit of the destination bits currently invented by Mesa FMA."""

import importlib.util
import json
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
ORIGINAL_BUILD_PROGRAM_FOR = R.build_program_for
OBS = {"pre_low": 1300, "pre_high": 1301,
       "post_low": 1310, "post_high": 1311}
TARGETS = (0, 16, 31, 32, 47, 48, 63, 64, 79, 80, 95)
SOURCE_TARGETS = (0, 15, 16, 31, 32, 47, 48, 63, 64, 79, 80, 95)


def build_cases(include_hazard=False, full=False):
    out = [{"i": slot, "name": "s0_slot%d" % slot, "arm": "S0",
            "kind": "s0_slot", "slot": slot, "expect_match": True,
            "predicted_bucket": "measure", "expect_sentinel": False}
           for slot in range(8)]
    for target in TARGETS:
        out.append({"i": len(out), "name": "fma_dstext_r%02d" % target,
                    "arm": "X", "kind": "fma_dstext", "target_reg": target,
                    "expect_match": True, "predicted_bucket": "measure"})
    for role in ("a", "b", "c"):
        for target in SOURCE_TARGETS:
            out.append({"i": len(out),
                        "name": "fma_src%s_r%02d" % (role, target),
                        "arm": "S", "kind": "fma_srcext", "role": role,
                        "target_reg": target, "expect_match": True,
                        "predicted_bucket": "measure"})
    return out


def _mutate_last_fma(pg, target):
    off, mnemonic, requested, data = pg.E.parts[-1]
    assert mnemonic == "falu3"
    b = bytearray(data)
    # Mesa's current alleged destination extension: instruction bits 22:23
    # and 60, i.e. byte 2 bits 6:7 and byte 7 bit 4.
    b[2] = (b[2] & 0x3f) | (((target >> 4) & 3) << 6)
    b[7] = (b[7] & 0xef) | (((target >> 6) & 1) << 4)
    pg.E.parts[-1] = (off, mnemonic, requested, bytes(b))


def _program(case, slots, carrier_len):
    target = case["target_reg"]
    low = target & 15
    srcs = [r for r in range(2, 10) if r != low][:3]
    src_a, src_b, src_c = srcs
    store_index, load_index = R.choose_indices({low, target, *srcs})
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    seeds = {low: 119, src_a: 120, src_b: 121, src_c: 122}
    if target != low:
        seeds[target] = 118
    R.seed_map(pg, load_index, store_index, seeds)
    low_before = pg.rbits(low)
    high_before = pg.rbits(target)
    R.observe(pg, store_index, low, OBS["pre_low"], "pre_low")
    R.observe(pg, store_index, target, OBS["pre_high"], "pre_high")
    result = R.fma_bits(pg.rbits(src_a), pg.rbits(src_b), pg.rbits(src_c))
    pg.body_start = pg.E.off
    R.emit_fma(pg, low, src_a, src_b, src_c)
    _mutate_last_fma(pg, target)
    pg.body_end = pg.E.off
    # Canonical-low model is used only to keep a complete oracle; the custom
    # scorer below separately distinguishes low, extended, and corrupt writes.
    pg.set_reg(low, result)
    R.observe(pg, store_index, low, OBS["post_low"], "post_low")
    R.observe(pg, store_index, target, OBS["post_high"], "post_high")
    pg.ext_expected = {"target": target, "low": low, "result": result,
                       "low_before": low_before, "high_before": high_before}
    return pg, pg.finish(carrier_len)


def _source_program(case, slots, carrier_len):
    target = case["target_reg"]
    alias = target & 63
    role = case["role"]
    destination = next(r for r in range(2, 12) if r not in (target, alias))
    others = [r for r in range(2, 12)
              if r not in (target, alias, destination)][:2]
    store_index, load_index = R.choose_indices({target, alias, destination, *others})
    pg = P.Prog(slots, case["name"], offnatural=False)
    pg.movi(store_index, 0)
    pg.movi(load_index, 0)
    pg.movi(P.R_SENT, P.SENT_IMM)
    pg.store(P.R_SENT, P.SENT_OFF, index_reg=store_index, tag="sentinel")
    seeds = {alias: 116, destination: 119, others[0]: 120, others[1]: 121}
    if target != alias:
        seeds[target] = 118
    R.seed_map(pg, load_index, store_index, seeds)
    vals = {"a": others[0], "b": others[1], "c": others[0]}
    vals[role] = alias
    high_result = None
    if target < 96:
        hvals = dict(vals); hvals[role] = target
        high_result = R.fma_bits(pg.rbits(hvals["a"]), pg.rbits(hvals["b"]),
                                 pg.rbits(hvals["c"]))
    alias_result = R.fma_bits(pg.rbits(vals["a"]), pg.rbits(vals["b"]),
                              pg.rbits(vals["c"]))
    pg.body_start = pg.E.off
    R.emit_fma(pg, destination, vals["a"], vals["b"], vals["c"])
    off, mnemonic, requested, data = pg.E.parts[-1]
    b = bytearray(data)
    if target >= 64:
        if role == "a": b[7] |= 0x01
        elif role == "b": b[7] |= 0x04
        else: b[4] |= 0x40
    pg.E.parts[-1] = (off, mnemonic, requested, bytes(b))
    pg.body_end = pg.E.off
    # Keep a complete alias oracle; classification is independent below.
    pg.set_reg(destination, alias_result)
    R.observe(pg, store_index, destination, OBS["post_low"], "post_result")
    pg.ext_expected = {"target": target, "alias": alias, "role": role,
                       "high_result": high_result, "alias_result": alias_result}
    return pg, pg.finish(carrier_len)


def build_program_for(case, slots, carrier_len):
    if case["arm"] == "S0":
        return ORIGINAL_BUILD_PROGRAM_FOR(case, slots, carrier_len)
    if case["kind"] == "fma_srcext":
        return _source_program(case, slots, carrier_len)
    return _program(case, slots, carrier_len)


def score_ext(case, pg, prog, rows, bad, alias, res, base_state, oracle,
              slots, dispatched_ok):
    rec = R.BASE_SCORE(case, pg, prog, rows, bad, alias, res, base_state,
                       oracle, slots, dispatched_ok)
    if case["kind"] != "fma_dstext":
        if case["kind"] == "fma_srcext":
            got = R.read_word(res, slots["out"], OBS["post_low"])
            e = pg.ext_expected
            model = ("extended_high" if got == e["high_result"] else
                     "canonical_alias" if got == e["alias_result"] else
                     "other_or_corrupt")
            rec["source_extension_probe"] = {"observed_result": got,
                                               "expected": e, "model": model}
        return rec
    obs = {k: R.read_word(res, slots["out"], v) for k, v in OBS.items()}
    e = pg.ext_expected
    if obs["post_low"] == e["result"] and obs["post_high"] == (
            e["result"] if e["target"] == e["low"] else e["high_before"]):
        model = "canonical_low"
    elif e["target"] != e["low"] and obs["post_high"] == e["result"] \
            and obs["post_low"] == e["low_before"]:
        model = "extended_high"
    else:
        model = "other_or_corrupt"
    rec["destination_extension_probe"] = {"observed": obs,
                                           "expected": e, "model": model}
    return rec


R.build_cases = build_cases
R.build_program_for = build_program_for
B.C = R
B.score = score_ext
raise SystemExit(B.main())
