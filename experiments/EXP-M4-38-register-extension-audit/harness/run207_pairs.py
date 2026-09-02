#!/usr/bin/env python3
"""Run exact Mesa get_sr destination encodings in EXP-0207's dump carrier."""
import copy
import sys
from pathlib import Path

H = Path("/Users/nsheth/agx-re/experiments/EXP-0207-g17p-frag-raster-sysval/harness")
sys.path.insert(0, str(H))
import plan207
import run207

base = next(a for a in plan207.ARMS if a["arm"] == "sr_dump")
arms = []
for target in (0, 16, 32, 48, 64, 80):
    a = copy.deepcopy(base)
    a["arm"] = "sr_pair_%02d" % target
    a["why"] = "Exact destination bytes currently emitted by Mesa for r%d" % target
    a["pair_target"] = target
    a["fields"] = []
    arms.append(a)
run207.SP.ARMS = arms

original_build = run207.build_archive
def paired_build(arm, workdir, cache=None):
    compile_arm = copy.deepcopy(base)
    archive, log = original_build(compile_arm, workdir, cache)
    hx = run207.extract_hex(compile_arm, archive)
    rel, _, _ = run207.resolve_anchor(compile_arm, hx)
    absolute = run207.locate(compile_arm, archive) + rel
    target = arm["pair_target"]
    block = bytearray(bytes.fromhex(hx)[rel:rel + 4])
    block[0] = ((target & 15) << 4) | 0x04
    block[2] = 0x50 if target >= 64 else 0x10
    block[3] = 0x06 | (((target >> 4) & 7) << 5)
    out = str(Path(workdir) / (arm["arm"] + "_paired.bin"))
    run207.splice(archive, out, absolute, bytes(block))
    return out, log
run207.build_archive = paired_build
raise SystemExit(run207.main())
