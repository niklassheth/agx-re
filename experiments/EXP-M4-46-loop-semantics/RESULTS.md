# EXP-M4-46 results: Apple9 structured loop control

Target: T8132 / Apple M4 (G16G), Mac16,10, macOS 26.6.2 build 25G83.
All inspected machine code is `_agc.main` compiled from the MSL in this
directory.  No Apple framework, launch helper, or proprietary binary was
disassembled.

## Result

Apple9 loops are a small structured execution-mask machine, not an arbitrary
branch ISA and not a special collection of source-language templates.  The
same core model covers top- and bottom-tested loops, zero-trip loops, divergent
per-lane trip counts, nested loops, `break`, `continue`, loop-carried scalar and
vector values, and loads inside a loop.

Nineteen fresh programs each matched all 64 output words against an independent
CPU oracle: 1,216 exact words total.  The input includes lanes with 0, 1, and 37
iterations, unequal nested trip counts, source breaks at different iterations,
lanes that take different continue paths, and a loop with two independently
dynamic latch conditions.  A separate safe machine-code
ablation retargeted a backedge to a decoded loop-pop instruction and matched its
changed exact oracle.

This is enough evidence to implement ordinary structured NIR loops without
copying captured register assignments.  The remaining unknown fields are
scheduling refinements and optimized predicate/mask algebra, not holes in the
basic correctness model.

## The branch instructions

The two ten-byte instructions are best named by execution-mask behavior:

```text
0f 00 54 <signed offset48> 00    JMP_EXEC_ANY
0f 01 54 <signed offset48> 00    JMP_EXEC_NONE
```

`JMP_EXEC_ANY` is the loop backedge.  It branches while at least one lane in the
current loop mask remains active.  Lanes that have completed stay masked while
other lanes continue.

`JMP_EXEC_NONE` follows a mask-narrowing operation.  It skips an empty loop,
conditional arm, or post-break region when no lane remains active.  It is a
uniform control transfer decided from the current lane mask, not a per-lane
branch carrying its own scalar Boolean operand.

Both offsets are signed 48-bit byte displacements relative to the **start of
the branch instruction**:

```text
target = branch_start + sign_extend(offset48)
```

The old `PC+4` description was wrong.  All 33 broadly decoded corpus backedges
land on instruction boundaries under the start-relative rule and none do under
`PC+4`.  In the fresh `pc_base_probe`, the native branch is at `0x84` with
offset `-58`, targeting `0x4a`; `PC+4` would land inside an instruction.
Changing the offset to `+10` targeted the loop pop at `0x8e` and produced the
exact expected one-iteration recurrence.  A `PC+4` implementation would have
landed four bytes into that six-byte pop.

## Canonical loop shape

A top-tested divergent loop has this structural form:

```text
compare entry condition
push/narrow entry mask
JMP_EXEC_NONE exit
prepare carried values
push loop scope                       0f 05 54/56 1a

header:
    body
    prepare carried-value edge copies
    compare continue condition
    update current loop mask          8f 04 54 <mask selector>
    JMP_EXEC_ANY header

pop loop scope                        0f 06 04 02 00 00
pop entry/conditional scope           0f 06 04 01 00 00
exit:
```

A bottom-tested loop starts at `header` without an entry guard.  The fresh
`do_bottom` program has the same mask update, `JMP_EXEC_ANY`, and kind-2 pop,
and correctly executes once when the requested count is zero.

The source forms `while`, `for`, and a literal `while (true)` with an explicit
conditional break normalize to the same canonical structure when their
semantics are equivalent.  Therefore Mesa should lower NIR structure, not try
to preserve source-loop syntax.

## The `8f` loop operations are not returns

The old database decoded these words as invalid `ret` link modes.  Fresh native
loops execute them successfully on T8132; substituting them at an actual
function return faults because that is a different instruction context.

The ordinary four-byte loop-mask update is:

```text
8f 04 54 <mask selector>
```

The selector contains at least two pieces.  Its low depth subfield is `0x02` at
the outer loop, `0x06` one mask scope deeper, and `0x0a` two scopes deeper.
Fresh one-, two-, and three-level loops produce `0x22`, `0x26`, and `0x2a` at
their respective latches.  The broad corpus contains 326, 196, and one raw
occurrences of those exact words.  A direct source `break` under one conditional
also uses the depth-2 `0x26` form before `JMP_EXEC_NONE`.

Bit `0x20` is orthogonal to that depth subfield and is semantic.  The broad
own-source corpus uses both `0x02` and `0x22` at outer latches.  Its `0x02`
examples are compound loop conditions, including `v != 1 && steps < 1000`,
`j < count && !stop`, and `j < count && found < 0`.  The fresh
`compound_latch` case independently emits `0x02` and passes its exact oracle.
On a native `0x22` loop, changing only this bit to `0x02` collapses almost every
lane to one iteration.  The reverse `0x02 -> 0x22` change on `compound_latch`
hangs the command buffer; that arm was stopped after the first hang.  This is
consistent with predicate/mask-source selection or polarity, not a disposable
lifetime flag.  The exact distinction between predicate identity and polarity
is deliberately left bounded.

Mutating the direct-break `0x26` to `0x22` completed but changed both control
and carried state, exactly as expected when the wrong mask level is updated;
it did not act like a harmless register rename.

The six-byte form performs a nonlocal break through nested mask scopes:

```text
8f 05 54 <scope-depth tag> 00 <target-loop depth>
```

Three orthogonal native cases isolate the useful fields:

| Source structure | Native bytes |
|---|---|
| break under one `if`, single loop | `8f 05 54 03 00 01` |
| break under two `if`s, single loop | `8f 05 54 04 00 01` |
| break under one active conditional, inner loop of two | `8f 05 54 03 00 02` |

All three passed exact hardware oracles.  Increasing conditional nesting changes
byte 3; changing the target loop level changes byte 5.  Matching linear
`pop_reconverge` instructions remain in the stream after the update.

## Nested loops and the mask stack

The triple-nested program establishes the recursive pattern directly:

```text
inner latch:   8f 04 54 2a ; JMP_EXEC_ANY inner_header ; pop kind 2
middle latch:  8f 04 54 26 ; JMP_EXEC_ANY middle_header; pop kind 2
outer latch:   8f 04 54 22 ; JMP_EXEC_ANY outer_header ; pop kind 2
```

Each guarded nested region also has its own kind-1 pop.  This is a hardware LIFO
mask stack; no fixed practical nesting limit was found or imposed here.

The earlier claim that byte 2 alternates `0x54/0x56` with nesting parity is
refuted.  One two-level capture happens to use `0x56` on a loop push, but the
fresh three-level loop uses `0x54` at all three depths.  Changing the
`pc_base_probe` latch from `8f 04 54 22` to `8f 04 56 22` preserves all 64
output words.  Across Apple9 families this bit behaves like a cache/lifetime
or scheduling form, but the condition that makes Metal select it remains open.
A correctness-first loop emitter can use the hardware-validated `0x54` form
for the basic cases here; general pressure-sensitive selection is later work.

## Break and continue

A direct conditional break uses the ordinary current-mask update at the mask
depth containing the break condition, followed by `JMP_EXEC_NONE` to the loop
pop/exit.  A break underneath additional conditionals uses the six-byte
`break_mask_unwind` form above.  This parallels the public Apple8 compiler's
*conceptual* lowering: simple breaks update the current execution mask, while a
deeper break carries a nesting/target depth.  Apple8's r0l counter and binary
encodings are not reused.

Continue is not a distinct mandatory opcode.  Metal if-converts the simple
case, and the observable nested case uses ordinary mask narrowing, empty-mask
skips, and reconvergence before the normal loop latch.  A general compiler can
therefore treat continue as an edge to the loop's continuation/latch block,
resolving carried values on that predecessor and unwinding the intervening
conditional masks.  Native mask algebra can be optimized later.

## Values, loads, and loop boundaries

The pair and four-component recurrence tests prove that loop-carried state lives
in ordinary allocated GPRs.  Metal emits edge moves/copies before the mask update;
there is no capture-fixed register tuple or magic machine `phi` instruction.
Mesa should use normal loop phis plus predecessor-edge parallel copies, the same
architecture already used for if/else joins.

`loop_device_load` issues a dynamic device load in every iteration and matches
all outputs through 37 per-lane iterations.  Native code consumes or publishes
the asynchronous result before the latch.  The existing correctness invariant
remains appropriate: no unresolved scoreboard result may cross a mask boundary
or backedge.  This does not prohibit loads in loops; it only requires their
handoff/materialization within the iteration.

## Compiler-facing model

The initial compiler implementation should:

1. Walk structured NIR recursively and maintain a loop stack plus current mask
   depth.
2. Create explicit header, continue/latch, and break/exit labels.
3. Resolve header phis with predecessor-edge parallel copies on the entry and
   backedge; resolve exit values on each breaking edge.
4. Finish pending scoreboard values before every mask operation or branch.
5. Emit `JMP_EXEC_ANY` for backedges and `JMP_EXEC_NONE` after mask narrowing.
6. Track the mask selector as a depth subfield plus a separate predicate/mask
   selection bit; use the six-byte unwind form when a break crosses nested mask
   scopes.
7. Lower continue as an edge to the latch, not as an invented special opcode.
8. Patch signed start-relative byte displacements only after final instruction
   sizes are known.

The public Apple8 CFG lowering is useful architecture for structured blocks,
phis, break targets, and continuation blocks.  Its execution-counter register
and encodings are generation-specific and must not be copied into Apple9.

## Bounded unknowns

These do not block ordinary structured loops:

- the exact performance/lifetime meaning of control forms `0x54` versus `0x56`;
- whether selector bit `0x20` names predicate identity, polarity, or a coupled
  mask-source choice (it is proven semantic and distinct from the depth bits);
- optimized mask-union sequences for complex short-circuit control flow;
- irreducible CFGs, arbitrary gotos, and exotic early-return/call interactions.

The implementation should preserve these as explicit generation-specific fields
instead of inventing semantics.  The canonical forms above are sufficient for
correct structured compute loops.

## Artifacts

- `loop_semantics.metal`: 19 own-source native programs.
- `run_native.py`: exact 16-lane CPU oracles and Metal execution.
- `run_ablations.py`: safe backedge retarget plus mask-selector and form tests.
- `analyze_native.py`: extraction and control-flow topology.
- `corpus_census.py`: 1,080-program broad corpus census.
- `LOOP_MODEL.json`: concise machine-readable model.
- `raw/native_results.json`, `raw/native_analysis.json`,
  `raw/ablation_results.json`, and `raw/corpus_census.json`: complete results.

Pinned source SHA-256 after the final hardware run:

```text
loop_semantics.metal  f4f26b58ed2e7f7dc112957b753a79755cecb8a5198481e3c9bc0609a370b64f
run_native.py         898a81f7349593e1e2a0751d1ea5017959ff6ff0d075baac474b4533776b8c7f
```

The raw result files retain every exact output and machine-code image.
