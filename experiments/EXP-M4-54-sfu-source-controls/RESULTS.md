# EXP-M4-54: SFU operand controls

Measured on Apple M4 / T8132 / G16G, macOS build 25G83, 2026-09-04.
**98 dispatches, 1,568 arithmetic/lifetime checks, zero mismatches or faults.**
These are sampled semantic checks, not exhaustive numerical accuracy tests.

## Finding

The source-release difference is real, but it belongs to two different operand
layouts. Grouping all ten-byte `0x2f/0xaf` instructions under one `fspecial`
descriptor had encouraged transferring reciprocal's operand controls to other
functions. Multiple fields differ, not just release.

| Control | Accurate reciprocal form | Ordinary SFU form |
|---|---|---|
| Release source | byte 6 bit 4 | byte 6 bit 5 |
| Source type | byte 7 bits [3:2] | byte 6 bits [4:3] |
| Measured type codes | 0 BF16, 1 FP16, 2 FP32 | 0 BF16, 1 FP16, 2 FP32 |
| Absolute source | byte 8 bit 6 | byte 7 bit 7 |
| Negate source | not resolved here; Metal used a separate operation | byte 8 bit 0 |

The source-type fields are supported by matched native narrow-input/wide-result
shaders and numerical execution. The release fields additionally have destructive
mutations. Absolute/negate fields have native diffs; ordinary-SFU mutations use
mixed-sign inputs to distinguish input modification from output modification.
Other operand/result controls, including narrow register addressing, are not
generalized by this experiment. The hardware-design reason for choosing these
layouts remains unknown; no separate physical SFU pipeline is inferred.

## Why `0xa0` looked like a broken retained-source form

For an ordinary SFU with an FP32 result:

| Source format | Retain, byte 6 | Release, byte 6 |
|---|---:|---:|
| BF16 | `80` | `a0` |
| FP16 | `88` | `a8` |
| FP32 | `90` | `b0` |

Native half-to-half forms instead use `8c/ac` and other result-control changes.
These are not conflicting release rules: bit 5 still changes lifetime.

Clearing bit 4 in `b0` selects BF16 and leaves release enabled. It reads the low
16 bits at the chosen source address. For example, the packed 32-bit input
`0x40003c00` has three deliberately different candidate interpretations:

- FP32: approximately 2.0036621;
- low FP16 `0x3c00`: 1;
- low BF16 `0x3c00`: 1/128.

Changing only byte 6 to `a0` makes log2 return **-7**, rsqrt return approximately
**11.313708**, and floor return **0**, matching low BF16. Across eight packed
inputs and four functions, the BF16 oracle passes all 32 outputs. The paired
`b0` controls compute on the FP32 word. Native `float(bfloat_input)` cases emit
the same `a0` source format and produce the expected FP32 results.

The prior Mesa tests commonly used FP32 values whose low 16 bits were zero, so
mis-selecting BF16 made the SFU see zero. This was unrelated to pending inputs.
The hardware-record tag `a0_packed_half` preserves the original pre-measurement
half hypothesis; `verify.py` explicitly checks the subsequently identified
**BF16** model, not IEEE half.

## Lifetime is independently observed

Each native reuse kernel stores `f(x)` and later `x + bias`. The canonical
retained form preserves both. Mutating only the appropriate release bit leaves
`f(x)` correct but changes every later `x + bias` result to `bias`, demonstrating
that the source was released to zero.

This passes for reciprocal, rsqrt, exp2, log2, and floor, using both float and
half source/result kernels: ten independent destructive controls. Native
BF16-to-FP32 reuse kernels also confirm `80` for the ordinary SFU and `00` for
reciprocal. The generated SFUs immediately consume a pending load through slot
6, so neither correct retention nor forced release depends on materialization.

The reciprocal corpus often uses `02`. Mutating native retained `00` to `02`
preserves the result and the later source read; `12` still releases the source.
Thus bit 1 does not replace or invert release bit 4 in these tests. Its wider
meaning remains unknown; it is not promoted as globally inert.

## The alleged NaN control is input negation

Native `rsqrt(-x)`, `exp2(-x)`, `log2(-x)`, and `floor(-x)` set byte 8 bit 0.
Mixed-sign mutations agree with evaluating the function on **-x**. In particular,
rsqrt/log2 become finite for negative original inputs and NaN for positive ones;
exp2 returns the expected positive powers of two in both directions.

The EXP-0161/0165 tests used positive finite rsqrt/log2 inputs. Their NaN
observations were correct, but the inference that bit 0 must never be emitted
was not. Byte 7 bit 7 applies **absolute value to the input**, not log2 negation.
These corrections are measured on T8132; a repeat on G17P was not performed.

## Corpus and evidence

`census.py` visited 35,341 public-source archives and deduplicated 30,569 mains.
The legacy length walker stopped early in 25,591 mains: this is a prefix census,
not complete coverage. It supplies raw counterexamples to treating `a0` as
invalid, including `g1_Powerbfloat16` from MLX and bfloat Bessel kernels from
PyTorch. Their provenance and offsets are retained in `CORPUS.json`.

Fresh own-source evidence removes dependence on the corpus's incomplete decoder:

- `source_controls.metal`, `capture.py`, `native/`, `NATIVE.json`: 50 matched
  float/half store, reuse, ALU-produced, negated, and absolute-source shaders.
- `measure.py`, `measurements/`, `HARDWARE.json`: those 50 native executions
  and 28 isolated mutations/paired controls. Every run requires archive-backed
  pipeline creation and checks command completion before consuming outputs.
- `mixed.metal`, `mixed.py`, `mixed/`, `MIXED.json`: 20 native BF16/FP16-input,
  FP32-output store/reuse shaders with independent numerical checks.
- `verify.py`, `VERIFICATION.json`: independent host arithmetic, explicit NaN
  classification, exact later-source checks, and at most two ULPs for approximate
  function results. Rounding operations and lifetime observations are exact.

Only project/public shader mains were inspected or modified. No Apple-authored
binary, launch program, constant program, or library implementation was inspected.

## Reproduction and updates

On the Metal target, place `agxparse.py`, `shdump`, and `agxrun` under `tools/`.
The latter two are built from this repository's own Objective-C sources with
`clang -fobjc-arc -framework Metal -framework Foundation`. Then run:

```sh
python3 capture.py
python3 measure.py
python3 mixed.py
python3 verify.py
```

`PLAN.md` records the initial hypotheses. `update_db.py` corrects only descriptive
metadata for `fspecial`; descriptor matching, field geometry, and emitted bytes
are unchanged. The Markdown/XML tables are regenerated from that database and
the ISA round-trip tests pass. Mesa's existing corrected FP32 encoding remains
unchanged; its comments and compute documentation now explain the BF16 selection.
