#!/usr/bin/env python3
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "raw"


def rows(name):
    return [json.loads(line) for line in (ROOT / name / "sweep.jsonl").read_text().splitlines()]


def require(condition, message):
    if not condition:
        raise SystemExit("FAIL: " + message)


descriptor_expect = {
    "isel_descriptor": 528,
    "ilogic_descriptor": 272,
    "fma_descriptor": 400,
}
for name, count in descriptor_expect.items():
    rs = [r for r in rows(name) if r.get("arm") not in ("S0", "CTL")]
    require(len(rs) == count, f"{name}: expected {count} positives, got {len(rs)}")
    require(all(r.get("status") == "OK" and r.get("match") is True for r in rs),
            f"{name}: positive mismatch")

fma_d = [r["destination_extension_probe"]["model"] for r in rows("fma_destination_split")
         if "destination_extension_probe" in r]
require(fma_d.count("canonical_low") == 1 and fma_d.count("extended_high") == 10,
        "FMA destination split")

fma_s = [r for r in rows("fma_source_split") if "source_extension_probe" in r]
fma_s_hi = [r for r in fma_s if r["source_extension_probe"]["expected"]["target"] >= 64]
require(len(fma_s_hi) == 12 and
        all(r["source_extension_probe"]["model"] == "extended_high" for r in fma_s_hi),
        "FMA high sources")

li = [r for r in rows("logic_isel_split") if "audit_probe" in r]
groups = collections.defaultdict(list)
for r in li:
    groups[r["kind"]].append(r)
require(sum(r["audit_probe"]["model"] == "extended_high" for r in groups["logic_dst"]) == 10,
        "logic high destinations")
logic_hi = [r for r in groups["logic_src"] if r["audit_probe"]["expected"]["target"] >= 64]
require(len(logic_hi) == 8 and all(r["audit_probe"]["model"] == "extended_high" for r in logic_hi),
        "logic high sources")
isel_hi = [r for r in groups["isel_src"] if r["audit_probe"]["expected"]["target"] >= 64]
require(len(isel_hi) == 16 and all(r["audit_probe"]["model"] == "extended_high" for r in isel_hi),
        "ISEL high sources")

sr = {r["arm"]: r for r in rows("getsr_exact_pairs") if r.get("kind") == "baseline"}
for a in ("sr_pair_16", "sr_pair_32", "sr_pair_48"):
    require(sr[a]["observed"]["d"] == sr["sr_pair_00"]["observed"]["d"] and
            sr[a]["observed"].get("clobbered_codeword_slots") == [], a)
require(sr["sr_pair_64"]["observed"]["d"] == sr["sr_pair_80"]["observed"]["d"],
        "get_sr r64/r80 collapse")
require(sr["sr_pair_64"]["observed"].get("clobbered_codeword_slots") == [8] and
        sr["sr_pair_80"]["observed"].get("clobbered_codeword_slots") == [8],
        "get_sr alternate bank")


def require_alu_split(run, op):
    rs = [r for r in rows(run)
          if r.get("alu_split_probe", {}).get("expected", {}).get("op") == op]
    require(len(rs) == 31, f"{op}: expected 31 probes, got {len(rs)}")
    require(all(r.get("status") == "OK" and r.get("outcome") == "ok" for r in rs),
            f"{op}: non-exact hardware result")
    models = collections.Counter(r["alu_split_probe"]["model"] for r in rs)
    require(models == {"low_control": 17, "extended_high": 14},
            f"{op}: split model counts {models}")


require_alu_split("g16_falu2_split01", "falu2")
require_alu_split("g16_falu2_extended_split01", "falu2_ext")
require_alu_split("g16_falu2_extended_split01", "falu2_srcmod10")
require_alu_split("g16_min_half_split01", "imin")
require_alu_split("g16_half_split02", "half")

print("PASS")
print("descriptor positives: ISELECT 528, ilogic 272, FMA 400")
print("split high positives: FMA dst 10/src 12; ilogic dst 10/src 8; ISELECT src 16")
print("compact ALU split positives: five forms x (dst 6/src 8), all exact")
print("get_sr: r16/r32/r48 collapse to r0 behavior; r64/r80 collapse to one alternate bank")
