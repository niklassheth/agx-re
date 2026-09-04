# EXP-M4-45 results: Apple9 predicate comparison and Boolean lowering

Target: T8132 / Apple M4 (G16G), macOS 26.6.2 build 25G83.  All shaders are
own-source MSL.  The experiment inspects only their `_agc.main` regions and
uses the public Metal API testbed.  It does not inspect proprietary Apple
helpers, wrappers, or framework binaries.

## Result

The old six-byte-only predicate model is wrong in several concrete ways.
There are at least a short ordered form and an extended ten-byte form;
comparison inversion, execution-mask inversion, and operand release are three
separate controls.  Native Metal can lower arbitrary Boolean conditions either
directly into mask-stack control flow or by materializing a 0/1 value and then
comparing it with zero.

All 39 native shaders matched complete 16-lane CPU oracles.  All 35 hardware
field/liveness ablations completed without a fault or hang and matched their
exact predicted output.

## Short ordered predicate compare

The basic register/register encoding is six bytes:

```text
byte 0       byte 1       byte 2       byte 3       byte 4      byte 5
0x0a|invert  srcA desc    control      srcB desc    condition   operand tail
```

Native examples with both sources dead after the comparison are:

```text
float  a > b   0a 03 3a 05 02 c0
float  a < b   0a 03 3a 05 03 c0
uint   a > b   0a 03 3a 05 04 c0
uint   a < b   0a 03 3a 05 05 c0
int    a > b   0a 03 3a 05 06 c0
int    a < b   0a 03 3a 05 07 c0
```

Changing only byte 4 in the unsigned-less-than carrier to `0x04`, `0x07`, or
`0x03` produced exact unsigned-greater-than, signed-less-than, or
float-less-than results respectively, including signed extremes, infinities,
signed zero, and NaNs.  This hardware-validates the condition-code map rather
than merely observing Metal choose it.

Immediate forms use the same base condition with bit `0x10` set.  Native,
hardware-correct examples include:

```text
uint a < 17u    0a 03 2a 90 15 c2
uint a >= 17u   0a 03 2a 90 04 c2  // Metal canonicalizes to a > 16
int  a < -7     0a 03 2a 0b 07 c2
float a < 0.5   0a 03 2a a1 03 c2
```

The compact immediate payload itself is not generalized by this experiment;
the production compiler can still materialize constants until that small
encoding is separately mapped.

### Inversion is not an operand bit

Changing byte 0 from `0x0a` to `0x1a` complemented every lane of both ordered
and equality comparisons.  Changing the following push from
`0f 05 54 01` to `0f 05 54 21` independently complemented every lane.  Making
both changes restored the original result.  Therefore:

- predicate-result inversion is byte 0 bit 4;
- execution-mask consumption inversion is push byte 3 bit 5;
- these are independent and may cancel.

The old interpretation of byte 0's high nibble as a predicate-register
destination is false for bit 4.  Only values zero and one were investigated;
the remaining high-nibble bits are not assigned semantics here.

### Operand release

The two last-use controls are in byte 2:

```text
base with both live:  0x22
release source A:     +0x08
release source B:     +0x10
extended form:        +0x01
```

The native short-form liveness quartet was:

```text
both live       0a 83 22 85 05 c0
A live          0a 83 32 05 05 c0
B live          0a 05 2a 83 05 c0
neither live    0a 03 3a 05 05 c0
```

On hardware, setting `0x08` caused a later source-A use to read zero; setting
`0x10` did the same for source B; setting both cleared both values.  This was
verified independently and together, with distinguishable source values.
The same source-A release behavior was reproduced on the extended equality
form.

Metal also sets byte 1/3 bit 7 in correlation with live-after operands, but
clearing those bits from native live-after programs did not affect either the
comparison or the later use.  Conversely, setting them in a dead-after program
did not preserve or clear anything.  Their precise meaning is therefore still
unknown; they are not the release controls.

## Extended predicate compare

Equality and ordered floating-point `<=`/`>=` use a ten-byte form.  The old
database splits its last four bytes into an unrelated instruction, which is
why its prior `cmpmode`/`neg` interpretation was misleading.

Every focused native instance has byte 2 bit 0 set and the next known mask
operation begins ten bytes after the predicate leader.  Representative native
sequences are:

```text
integer equality  0a 03 3b 05 06 00 07 c0 00 00
float equality    0a 03 3b 05 06 00 00 c0 00 00
float >= sequence 1a 03 3b 05 06 00 02 c0 00 00  + inverted push
float <= sequence 1a 03 3b 05 06 00 03 c0 00 00  + inverted push
uint == 17        0a 03 2b 90 06 00 17 c2 00 00
```

Hardware tests establish the useful distinctions:

- changing extended byte 6 from `0x07` to `0x00` changes integer/bitwise
  equality to IEEE floating equality; `+0.0 == -0.0` becomes true and equal
  NaN payloads become false;
- changing it back from `0x00` to `0x07` restores integer/bitwise equality;
- changing the native floating `>=` sequence's byte 6 from `0x02` to `0x03`
  changes the complete result to floating `<=`, including unordered cases;
- byte-2 source release controls work on this form exactly as on the short
  form.

This explains why native Metal does not implement floating `>=` as a naive
arm-swap of floating `<`: `!(a < b)` is true for unordered NaN inputs, while
ordered `a >= b` must be false.  The current Mesa path gets that corner case
wrong.

## How Metal handles arbitrary Boolean conditions

There is no single mandatory lowering.  Metal chooses among a few simple
strategies according to value use and short-circuit semantics:

1. **Direct relation:** a relational value used only by control flow becomes a
   predicate compare followed by a mask push.  `>`, `<`, equality, and their
   complements all use this path.
2. **Compare an arbitrary value with zero:** a bit test or arithmetic expression
   is evaluated into an ordinary GPR and consumed by the extended integer
   equality form plus a normal or inverted mask push.  The arithmetic-nonzero
   probe did exactly this and matched all lanes.
3. **Short-circuit AND:** Metal emits the first predicate, narrows the mask,
   skips the RHS when no lane needs it, evaluates the RHS only under that mask,
   and then enters the body.  `bool q = A && B; if (!q)` and the directly written
   `if (!(A && B))` produced byte-identical `_agc.main` programs.
4. **Short-circuit OR:** Metal evaluates the RHS only for lanes failing the
   first term and unions the two lane populations with mask operations before
   entering the body.  The named-variable and direct-source formulations again
   produced byte-identical `_agc.main` programs.  Some of the mask-union words
   are still misframed by the current database, so this experiment records the
   strategy without prematurely naming each sub-operation.
5. **Non-short-circuit composition:** Boolean XOR and a Boolean selected from
   two comparisons are materialized through compare/select operations as 0/1,
   combined as ordinary values, then compared with zero for control flow.
6. **Boolean fanout:** when the Boolean must be stored and also controls a later
   side effect, Metal emits a compare-select to materialize 0/1 for the store
   and separately re-emits a predicate comparison for the mask.  It does not
   treat the predicate as a generally reusable GPR Boolean.  When the separate
   side effect is removable, Metal can collapse the whole apparent branch to a
   select and emit no mask control at all.

An important corollary is that source spelling is not the model.  The compiler
must support both ordinary 0/1 Boolean SSA values and ephemeral predicate/mask
conditions, and may fuse between them when legal.

## Mesa consequence

The current Mesa code has three now-demonstrated modeling errors:

- it supports only the six-byte ordered form, so there is no equality predicate
  and no IEEE-correct floating `<=`/`>=` path;
- `AGX_APPLE9_PREDICATE_ALTERNATE_FORM` is attached to a source-descriptor high
  bit whose isolated mutation is semantically inert in these tests;
- the packer fixes byte 2 to `0x22`, retaining both sources rather than deriving
  release bits from VIR liveness.

The correctness-first implementation order should be:

1. represent predicate-result inversion, mask-consumer inversion, source
   release, and relation as independent properties;
2. add the short ordered and extended equality/float-complement encodings;
3. directly fuse supported relational NIR conditions;
4. add the general fallback: materialize any supported Boolean expression as
   0/1 and use the native integer compare-to-zero predicate sequence;
5. preserve NIR control flow for short-circuit/side-effecting expressions;
6. later optimize pure Boolean trees into native mask algebra where profitable.

That fallback expands condition support without needing to decode the entire
native OR mask-union sequence first.

## Artifacts and reproduction

- `predicate_conditions.metal`: the own-source corpus.
- `run_native.py`: 39 exact native hardware oracles.
- `run_ablations.py`: 35 exact field/lifetime mutations.
- `analyze_archives.py`: extraction plus an experiment-local corrected framing
  view (it does not silently rewrite the global ISA database).
- `PREDICATE_MODEL.json`: concise machine-readable model.
- `raw/native_results.json`, `raw/ablation_results.json`, and
  `raw/native_analysis.json`: raw results and complete extracted programs.

Pinned source SHA-256:

```text
predicate_conditions.metal  ad50bec85c67ef694284563d4f1b21d6d307063bc4601079742909f224e83f96
run_native.py               35d9c64204414b3550296ded6bd77f1f97fe5e58f4368ad689d19b58f2ff980a
run_ablations.py            c2ebaa11b377a1ec26aebfac0487581468ec1788fe67f13b59b44d6165ff8a75
analyze_archives.py         dcd34e96ccede84dc4b32e7439156ac3e24a002d2b89dd302ae6be69584f5b3e
```

The hashes above describe the hardware-run sources.  Recompute them if the
harness is edited; raw result files retain the exact outputs independently.
