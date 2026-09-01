# EXP-M4-31 results

> **Interpretation refinement:** EXP-M4-33 makes the prior consumer itself a
> decoded route-bearing instruction and follows one retained value through
> three reads.  It supersedes the global/recent-read-state interpretation in
> this file with a per-value transient-to-materialized handoff model.  The
> native route census here remains valid.  See
> `../EXP-M4-33-apple9-route-handoff/RESULTS.md`.

## Result

The simpler binary instructions reproduce the scheduling sensitivity seen in
`ISELECT`, and make its direction substantially clearer.  Apple9 instruction
bits 45–47 behave like a source-publication/return-route selection in these
native carriers:

- Changing only what consumes the binary result does not change the field.
- Independently reading a direct-return source before the binary instruction
  does change it.
- Ordinary system-derived GPR arithmetic uses route 0 in `falu2i`; Metal uses
  compact, field-less forms for ordinary-GPR `falu2` and XOR.

The result is not yet a proof that every numeric value has one universal name
across every opcode.  Direct atomic and threadgroup values do not use identical
numbers in every FALU and XOR form.  The common invariant is stronger than a
producer-class label, however: the value is stable under destination-use
changes and responds to the source's immediately preceding use/publication
state.

## Qualified native matrix

`—` means Metal selected a compact ordinary-GPR form without bits 45–47.
`same` and `IMAD` leave the source schedule untouched; `prior pN` adds an
independent read of that source before the target.

| Consumer | Producer | Direct | Duplicate result | Result → IMAD | Prior p0 | Prior p1 |
|---|---:|---:|---:|---:|---:|---:|
| `falu2i` | system GPR | 0 | 0 | 0 | 0 | n/a |
| `falu2i` | texture return | 1 | 1 | 1 | 0 | n/a |
| `falu2i` | atomic return | 6 | 6 | 6 | 0 | n/a |
| `falu2i` | threadgroup return | 6 | 6 | 6 | 0 | n/a |
| `falu2` | system GPR | — | — | — | — | — |
| `falu2` | texture returns | 1 | 1 | 1 | 2 | 2 |
| `falu2` | atomic returns | 6 | 6 | 6 | 1 | 1 |
| `falu2` | threadgroup returns | 1 | 1 | 1 | 6 | 1 |
| XOR | system GPR | — | — | — | — | — |
| XOR | texture returns | 1 | 1 | 1 | 2 | 2 |
| XOR | atomic returns | 0 | 0 | 0 | 1 | 1 |
| XOR | threadgroup returns | 0 | 0 | 0 | 1 | 1 |

Every table cell is stable across its two equivalent source formulations and
both precise/fast modes.  The full stage main is also stable between forward
and reverse fresh-process compilation.

## Why the prior-use comparison is controlled

For all 64 direct-target prior-use native cases, Metal emitted the same local
shape:

1. An `IMAD` reads p0 (`srcB=0`) or p1 (`srcB=16`).
2. One address `iadd2` intervenes.
3. The requested `falu2i`, `falu2`, or XOR consumes the original values.

Thus the MSL's apparent statement order is not being used as evidence.  The
actual Apple9 instruction order and source descriptor identify which return
value was read before the target.

The texture panel is the cleanest cross-family witness.  With no preceding
source read, `falu2i`, `falu2`, and XOR all use candidate route 1.  Reading the
only `falu2i` source first changes it to 0.  Reading either source of `falu2` or
XOR changes both to 2.  This is native route-2 use with texture producers and no
ordinary device-load producer in the experiment.

## Destination-use controls

Two controls changed the result lifetime without changing its inputs:

- Duplicate-result writes force two output stores.
- Result-to-IMAD makes the binary result feed integer arithmetic before the
  store.

The second control visibly changes other instruction state.  Native FALU
changes its publication/release flags, while native XOR changes from the
`0x1e` form to the corresponding `0x3e` downstream-consumed form.  Bits 45–47
remain unchanged in every producer panel.  This separates the candidate field
from those destination controls.

## Compact ordinary-GPR controls

Metal does not emit the full route-bearing register-register instruction for
the system-derived controls:

- Float addition becomes `falu_acc`.
- Integer XOR becomes a four-byte form currently decoded as `reg_move_cb`.

Their complete-output execution proves the terminal semantics, but the current
mnemonic for the compact XOR form should be treated as provisional.  `falu2i`
has no corresponding two-register compact normalization and uses candidate
route 0 for the same ordinary-GPR source class.

This suggests a simple hardware organization: compact instructions consume
ordinary register-file state, while the longer forms carry extra selection for
values still available through publication/return paths.

## Validation

- 56 semantic cases.
- 224 native cases: formulation A/B × precise/fast.
- 448/448 exact T8132 executions over complete 4-KiB buffers.
- 224/224 stage mains stable across forward/reverse fresh-process order.
- 112/112 equivalent formulation pairs compile to identical stage mains.
- 184 direct requested targets qualified.
- 40 native compact normalizations recorded.
- No candidate-route bit mutations were executed.
- Ordinary device-buffer loads were not used as a producer panel.

One oracle detail was discovered rather than hidden: lane 16 of the atomic
bitcast-float carrier is subnormal.  Native float ALU flushes that source to
zero.  The independent CPU oracle models that observed input flush; all other
atomic words remain independently distinguishable.

## Next question

The remaining asymmetry is narrow: direct atomic/threadgroup values can use 6
in FALU while the corresponding XOR uses 0, and threadgroup `falu2` responds
differently depending on which operand was read first.  The next useful native
experiment is not a route sweep.  It is a packet-level cross that holds the two
producer issue descriptors and physical return slots fixed while swapping only
the final FALU/XOR consumer.  That will distinguish a shared route numbering
from opcode-specific modifier composition.
