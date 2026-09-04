# EXP-M4-55: sqrt factor and sine factor

T8132 / Apple M4 / G16G, macOS 25G83, 2026-09-04. Own-source Metal only.
**27 successful dispatches; 29,184 numerical checks; zero mismatches or faults.**
Four native trig edge-case dispatches provide compiler context only and are
excluded from the numerical count; Metal's complete fast range reduction is
not the numerical oracle for this experiment.

## Class 1, family `2f`: a square-root multiplication factor

For the measured FP32 ordinary operand form:

```text
2f 01 56 00 02 00 b0 40 00 00
```

The result is approximately `1/sqrt(x)` for positive normal inputs, but is
**1** for both signed zeros and positive infinity. Negative normal inputs,
negative infinity, and NaNs yield NaN. Subnormal operands act as signed zero
in the tested arithmetic mode and therefore also return 1.

Consequently a normal multiply `x * sqrt_factor(x)` computes square root while
preserving signed zero and positive infinity. This explains the two-instruction
sequence emitted by Metal's `fast::sqrt`: the first instruction is not the
square root itself. The earlier positive-only function sweep could not
distinguish this helper from ordinary reciprocal square root.

| Input | `af` class 1: rsqrt | `2f` class 1: sqrt factor | `x * sqrt_factor(x)` |
|---|---:|---:|---:|
| +0 | +infinity | 1 | +0 |
| -0 | -infinity | 1 | -0 |
| +infinity | +0 | 1 | +infinity |
| 4 | 0.5 | 0.5 | 2 |
| negative normal | NaN | NaN | NaN |

The two factor instructions returned **bit-identical results on all 4,096
random positive-normal inputs**. Changing source-control byte 6 among
`90/92/b0/b2` did not change their edge-case arithmetic; source retention versus
release remains separately established by EXP-M4-54. In particular, byte 6 bit
1 is not responsible for the sqrt/rsqrt exception distinction.

As a sensitivity control, changing only `2f` to `af` inside native fast sqrt
preserves its ordinary multiply but makes zero and infinity results NaN.
Thus the exception behavior belongs to the factor instruction, not a special
zero-times-infinity multiplication rule.

## Class 3, family `2f`: sine evaluation factor, not range reduction

```text
2f 03 56 00 02 00 b0 40 00 00
```

The measured function is:

```text
sin_factor(x) = sin(pi*x/2) / x       for 0 < abs(x) <= 1
sin_factor(0) = pi/2                 for either signed zero
sin_factor(x) = NaN                  for abs(x) > 1, infinities, or NaNs
```

It is even: positive and negative inputs produce the same factor. Examples:

| x | Factor | x times factor |
|---|---:|---:|
| 0 | 1.57079637 | +0 |
| 0.125 | 1.56072259 | 0.19509032 |
| 0.25 | 1.53073370 | 0.38268343 |
| 0.5 | 1.41421354 | 0.70710677 |
| 1 | 1 | 1 |

The formula was predicted from EXP-0161's raw values before new hardware runs
(`PLAN.md`). A grid of 4,096 inputs spanning [-1,1), plus 4,096 randomized FP32
bit patterns and directed boundary/exception cases, agrees with the model.
Every finite in-domain factor is within **one ULP** of the double-precision
host formula rounded to FP32. Every sampled out-of-domain input returns NaN,
including the immediate representable neighbors outside +/-1. Reversing the
dense lane order reproduces all outputs bit-for-bit.

Replacing only the function class inside native fast sqrt turns its factor-plus-
multiply sequence into `x * sin_factor(x)`. It computes `sin(pi*x/2)` within
two ULPs over the 4,096-point grid, and preserves signed zero. Subnormal inputs
flush in the final ordinary multiply; a general sine lowering must still handle
tiny inputs explicitly when required by its numerical contract.

Metal's own sin, cos, sinpi, cospi, and tan captures all use this class-3 factor
after their preceding arithmetic. Tan uses it twice and subsequently uses
reciprocal. This instruction does not return a remainder or a quadrant: callers
must first reduce the argument and then apply the appropriate quadrant/sign.
The mirrored `af` class-3 form matches ordinary rsqrt on the tested edge vector.

## Compiler implications

The compiler model should distinguish `rsqrt`, `sqrt_factor`, and `sin_factor`
as separate semantic operations. A fast sqrt can use the measured factor and
multiply; stronger accuracy requirements may still require refinement.

Sine/cosine can use the sine factor for reduced-angle evaluation. This does not
replace full-range argument reduction, quadrant selection, tiny-input handling,
or precision work at the reduction/evaluation boundary. The follow-up Mesa integration below makes both helpers reachable from ordinary
shader operations, while retaining the independently constructed range reduction.

## Reproduction and provenance

- `assist.metal`, `capture.py`, `native/`, `NATIVE.json`: nine project-authored
  shaders compiled through the public Metal API, preserving raw main bytes.
- `probe.py`, `followup.py`, `raw/`, `HARDWARE.json`: isolated instruction
  mutations and native/composed controls, with full input/output bit patterns.
- `verify.py`, `VERIFICATION.json`: independent numerical/classification checks,
  the 4,096-value factor identity check, and reversed-order reproducibility.

On the Metal target, supply the project's own `shdump`, `agxrun`, and
`agxparse.py` under `tools/` (this run reused EXP-M4-54's built tools), then run
`capture.py`, `probe.py`, and `followup.py` in that order. Run `verify.py` on the
collected results. All executed pipelines require an archive hit. Only the
corresponding own-source `_agc.main` region is inspected or mutated. No
proprietary binaries were disassembled, and no native polynomial or
range-reduction sequence was copied into Mesa.

These are T8132 measurements over the recorded FP32 inputs. They are not an
exhaustive precision guarantee, a complete characterization of other source/
result datatypes, or a new G17P hardware run.

## Mesa integration follow-up

`mesa-m1n1-shim` now lowers ordinary FP32 `fsqrt` to `FSQRT_FACTOR` and a
multiply. Ordinary `fsin`/`fcos` keep the independently constructed 256-bit
fixed-point reduction, then evaluate the new `fsin_factor_agx` NIR operation
at the reduced phase and its complement. Two FMAs correct the small phase
residual and complement subtraction error. The previous Taylor polynomials
and explicit sqrt zero/infinity fixups have been removed. Both factors use
normal virtual operands, allocation, scoreboard dependencies, and liveness;
the original operand remains live until its multiply.

Validation on T8132:

- 180 compiler/allocator/packer tests and 4 geometry tests pass. Compiler tests
  check sqrt's class-1 `2f` encoding, sine factor's class-3 `2f` encoding,
  retained and final-use sources, pending and materialized operands, and two
  independent full-range trig expressions in the same shader.
- `tmp/apple9-factor-hw.log`: sqrt, materialized sqrt, full-range random sin/cos,
  and sin/cos quadrant-boundary tests: 6 cases pass.
- `tmp/apple9-factor-regression-hw.log`: dense sin/cos on [-pi,pi], the remaining
  14 SFU cases, and 3 reciprocal cases: 19 cases pass.
- `tmp/apple9-factor-compute-hw.log`: 6 general compute regressions pass,
  covering loaded float DAGs, vector ALU stores, reciprocal-based division,
  loops, and atomic pending-load forwarding.
- The 22 math cases check 360,448 output values plus immutable inputs and
  guards. Roots, exp2/log2, and trig retain the two-ULP sampled tolerance;
  rounding remains exact. No tolerance was relaxed for the factor lowering.

Log paths above are relative to `/home/nsheth/Projects/asahi`. These runs
compile normal GLSL through Mesa and execute through the m1n1 DRM shim.
