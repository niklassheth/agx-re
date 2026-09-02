# EXP-M4-38 — split register-field audit

This is an own-source, hardware-executed audit of four Apple9 instruction
families whose Mesa packers appeared to extend a compact register field with
bits elsewhere in the instruction:

- `falu3` / FP32 FMA;
- compact, extended, and source-modifier `falu2`;
- `ilogic`;
- integer min/max;
- native half ALU;
- `isel10`;
- `get_sr`.

Target: Apple M4 / T8132 / G16, macOS 26.6.2 (25G83).  G16 and G17 are
expected to share the ISA.  The G16 run is useful both as direct evidence and
as a check that earlier G17 conclusions were not accidentally transferred from
a generation-specific model.

The experiment first proves that generated `device_load`/`device_store`
programs can independently seed and observe r0..r95.  It then runs the older
descriptor-only matrices and, separately, exact encodings containing the
split high bits used by Mesa.  This distinction is essential: sweeping an
eight-bit operand descriptor while holding a separate high bit clear cannot
measure the complete register number.

`raw/` contains the complete dispatch records pulled from the target before it
was shut down.  `harness/` contains the small wrappers used for the split-bit
and exact-pair cases; they reuse the frozen generated-program machinery from
EXP-0207 and EXP-0231/0234/0235/0236.

The later compact-ALU extension consists of 155 exact-output cases across five
forms.  Each form covers destination banks through r95 and both source roles
with independently distinguishable rN and rN+64 contents.  The promoted half
run also models the observed half-register release granularity: consuming a
low half first clears that half, while a following ordinary store releases the
remaining word.

Run `python3 analyze.py` to verify the promoted counts and conclusions.
