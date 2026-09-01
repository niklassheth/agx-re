# Native Metal route census

> **Interpretation correction:** EXP-M4-33 separates the two co-varying fields
> in this experiment's preceding IMAD and replaces the global/recent-read
> cursor interpretation below.  The native correlations and execution results
> in this file remain valid, but they do not establish that the preceding read
> causes ISELECT's route transition.  See
> `../EXP-M4-33-apple9-route-handoff/RESULTS.md` for the hardware cross and the
> current per-value transient-to-materialized handoff model.

## Scope and controls

This result is native-only and contains no patched route values.  The initial
ALU panel does not source-author a direct device-load-to-ISELECT edge, although
Metal creates one by factoring an identical transformation out of both selected
arms.  The follow-up panel deliberately authors direct texture, atomic-return,
and threadgroup-return dataflow so the native route-1/route-2 transition can be
isolated at the instruction level.

The corpus contains 101 semantic source definitions.  Precise/fast math and two
equivalent source formulations produce 404 native cases.  Each was compiled
and run in both forward and reverse corpus order on T8132 under macOS 26.6.2
25G83.

- 808/808 full 4-KiB output comparisons passed.
- 404/404 extracted stage mains were byte-identical across compile order.
- 202/202 equivalent source-formulation pairs had identical stage mains.
- 370/404 stage mains are completely tokenized by the current local ISA DB.
- Incompletely decoded programs remain exact execution evidence but are not
  promoted into route claims.

`NATIVE_CENSUS.json` contains every source identity, archive identity, complete
decoded instruction record, route-field extraction, output hash, and the
qualification decision.

## Qualified ISELECT observations

The reviewed ISELECT field is bits 61..63, the upper three bits of the
instruction's scheduling-flags byte.

Ordinary integer ALU, predicate-materialization, and system-index ALU cases all
use native route 0.  The independently reproduced prior anchor uses route 2.
Both choices are stable across source formulation, math mode, and compilation
order.

The eight-case load-derived transition panel holds `p0` fixed and independently
chooses the anchor or varied expression for `p1`, `p2`, and `p3` in:

```metal
uint result = (p0 < p1) ? p2 : p3;
```

The mask bits correspond to `p1`, `p2`, and `p3`, respectively:

| Mask | Selected-arm shape | Native route | Stage-main bytes |
|---|---|---:|---:|
| 000 through 101 | at least one of `p2`, `p3` varied | 0 | 254 |
| 110 | `p2`, `p3` anchor; `p1` varied | 2 | 234 |
| 111 | `p1`, `p2`, `p3` anchor | 2 | 234 |

The assembly explains the otherwise surprising dependence on both arms.  For
the route-0 forms, Metal emits the XOR/add separately for `p2` and `p3`, then
selects the two completed values.  For masks 110 and 111 it applies the identity

```text
cond ? f(x) : f(y)  ==  f(cond ? x : y)
```

where `f(v) = (v ^ 0x13579bdf) + 0x10203`.  It selects the two raw load results
first and emits one shared XOR/add pair after ISELECT.  This removes exactly
two 10-byte instructions, accounting for the 254-to-234-byte change.

The operand encoding confirms the direct edge.  In the route-2 program, the
`p2` and `p3` device loads publish to r4 and r3 (`extmode` 8 and 6), and the
ISELECT true/false fields name encodings 8 and 6.  In the route-0 program, at
least one selected operand names the result of its pre-select ALU chain instead.

Five route-2 destination controls preserve route 2 when the selected result is
directly stored, stored twice, or also consumed by add, multiply, or rotate.
All 40 executions across precise/fast math, two formulations, and two compile
orders are exact.  This refutes the narrow explanation that route 2 merely
means “ISELECT has a later integer consumer.”

The system-only transition panel reproduces the same factoring threshold:
masks 000 through 101 have 180-byte mains and masks 110/111 have 150-byte
mains.  Nevertheless, every system-only ISELECT uses route 0.  Therefore the
route-2 choice is not implied by the algebraic optimization alone.  It appears
when the factored ISELECT directly consumes device-load destinations; the
system-only factored ISELECT consumes ALU-produced values and remains route 0.

## Float observations

Precise float selects use a completely decoded terminal ISELECT with route 0.
Several fast float selects contain a route-2 ISELECT candidate, but their stage
mains are not completely tokenized, so they are not promoted as evidence.

Ordinary float add and multiply commonly select a compact accumulator form
without this reviewed route field.  FMA cases contain a terminal
`falu2_uni` candidate with field value 0, but exact source-edge reconstruction
is still pending.  Intermediate `falu3` records contain values 0, 1, 2, 3, and
6; those instructions directly consume several device-load forms and are
outside this pass's deliberate boundary.

## Direct-return route-1/route-2 isolation

The decisive panel separates producer reuse from result combining.  Four
direct return values feed the same ISELECT.  One value is also multiplied by a
constant before ISELECT, but the multiplication result and the select result
are written to separate output regions.  Thus the extra IMAD does not consume
the ISELECT result and cannot be folded into its output expression.

For texture, atomic-return, and threadgroup-return producers, Metal emits the
same ISELECT bytes after clearing only bits 61..63:

```text
22 03 1f 05 82 0c 05 00 80 08
```

All other decoded ISELECT fields are identical.  Only the preceding IMAD source
and the three route bits change:

| Direct value also read by preceding IMAD | Texture | Atomic return | Threadgroup return |
|---|---:|---:|---:|
| `p0` | 2 | 2 | 2 |
| `p1` | 1 | 1 | 1 |
| `p2` | 1 | 1 | 1 |
| `p3` | 1 | 1 | 1 |

Every cell has two equivalent source formulations, precise/fast compilation,
forward/reverse compilation order, and complete exact-output execution.  The
transition is therefore not caused by one producer opcode family.

The texture controls remove several alternative explanations:

- Writing the ISELECT result twice, with no producer reuse, retains route 1.
- Storing the IMAD and ISELECT results separately retains the `2,1,1,1`
  transition, so it is not caused by merging their results.
- Rewriting `p0 < p1` as `p1 > p0` swaps the encoded comparison operands but
  preserves routes `1,2,1,3` for fanout masks `0,1,2,3`.
- Swapping the texture-coordinate recipes assigned to `p0` and `p1` also
  preserves `1,2,1,3`; the coordinate arithmetic and sampled value are not the
  discriminator.

Those controls still confound tuple identity with issue order: `p0` is the
first return issued.  A final panel swaps the first two producer statements.
Atomic operations preserve that source order, and the threadgroup form puts a
barrier between returns.  Route 2 moves with issue order:

| Producer order | Value read by preceding IMAD | IMAD source encoding | ISELECT route |
|---|---|---:|---:|
| `p0,p1,p2,p3` | `p0` | 4 | 2 |
| `p0,p1,p2,p3` | `p1` | 8 | 1 |
| `p1,p0,p2,p3` | `p0` | 8 | 1 |
| `p1,p0,p2,p3` | `p1` | 4 | 2 |

Both atomic-return and barrier-separated threadgroup-return programs reproduce
the table.  The assembly-level discriminator in this controlled shape is
therefore exact: route 2 is emitted when the immediately preceding IMAD reads
the first issued direct-return slot (the slot encoded as IMAD source 4) and
ISELECT reads that value again.  Route 1 is emitted when the preceding IMAD
reads the next issued slot (encoding 8), or the other later return slots, or
when there is no prior read.  It is not tied to the MSL variable, sampled
coordinate, producer family, or ISELECT operand position.

The broader texture fanout panel confirms that this field describes state of
the complete scheduled graph rather than a Boolean `p0 reused` flag.  Qualified
native routes for masks `0..a` and `c` are respectively
`1,2,1,3,1,3,3,4,1,2,1,1`; the most complex masks are excluded because the
current decoder does not completely tokenize those programs.  Multiple prior
uses change both texture-chain allocation and the route value.

## Raw versus materialized selected arms: matched 2x2

The original load-derived transition correlated route 2 with raw p2/p3
selected arms, but it changed too much of the scheduled program to establish
that the selected-arm producer form caused the route.  A matched atomic-return
2x2 now separates that axis from the prior p0/p1 read:

| ISELECT selected arms | Immediately prior extra read | Native route |
|---|---|---:|
| Raw p2/p3 returns | First-issued p0, source 4 | 2 |
| Raw p2/p3 returns | Second-issued p1, source 8 | 1 |
| Distinct p2/p3 IMAD results | First-issued p0, source 4 | 2 |
| Distinct p2/p3 IMAD results | Second-issued p1, source 8 | 1 |

The materialized cells emit the final direct return at offset 178, distinct
p2/p3 IMADs at offsets 200 and 212, the controlled p0/p1 reuse IMAD at offset
224, and ISELECT immediately after it at offset 236.  The raw cells contain
only the controlled reuse IMAD between the final return and ISELECT.  All four
ISELECTs reduce to the same bytes when bits 61..63 are cleared:

```text
22 03 1f 05 82 0c 05 00 80 08
```

The two materialization constants differ, so Metal cannot factor a common
operation after the select.  Both equivalent source formulations and both math
modes produce identical stage mains, and every forward/reverse execution
matches the full oracle.

This disproves the simple interpretation that route 2 is selected because the
ISELECT selected arms themselves are raw asynchronous returns.  In this fixed
schedule, changing those arms from direct returns to ordinary IMAD results has
no effect; changing which numbered return slot was read immediately beforehand
still changes route 2 to route 1.  The older raw-arm correlation was therefore
a property of a larger scheduling/publication-state change, not a provenance
rule for p2/p3 alone.  The remaining candidates include producer publication
descriptors, release state, and the complete live return graph.

The most economical hardware model is a dynamic-return/cache route or cursor.
In the isolated texture programs, the four `tex_sample` instructions publish
on numbered chains, the extra IMAD consumes one returned value, and ISELECT's
three-bit field changes to match the resulting consumer state.  That model is
strongly supported but not yet a universal proof of the field's semantics in
every instruction family.  What is proven is the native compiler rule above;
`route 1` is not a producer class and does not mean that the input is an
ordinary register value.

## Original route-2 mystery and broader native audit

The earlier claim that an “ALU result” reached ISELECT with route 2 was a
source-level misclassification.  Every completely decoded ordinary-ALU case in
this corpus that reaches route 2 has been factored so that the ISELECT actually
reads raw device-load destinations.  The precise float forms that use route 0
perform their per-value `falu3` transformations before ISELECT.  They are not
the same instruction-level producer/consumer edge.

Route 2 is not exclusive to device-buffer loads, however.  Three older
own-source native compute cases were re-audited at the instruction level:

| Direct ISELECT producer | Producer instruction sequence | Native route |
|---|---|---:|
| Texture read | Four `tex_sample` returns, then ISELECT | 2 |
| Atomic return | Four atomic-return sequences, then ISELECT | 2 |
| Threadgroup read | Threadgroup-space loads, then ISELECT | 2 |

For each row, both source formulations and both compilation orders have
byte-identical stage mains, and all four full-output hardware executions match
their exact oracle.  There is no intervening ordinary ALU transformation of
the selected pair.

The number is not a fixed producer-type code.  The controlled split-store panel
above shows exactly why the earlier texture, atomic, and threadgroup cases
divide between route 1 and route 2: it is the preceding read of one member of
the direct-return tuple, not the producer family.

No clean native example in the audited corpus currently establishes route 2
for an ISELECT pair produced solely by ordinary register ALU instructions.
System-only ALU controls use route 0; source cases previously labelled as
ALU-to-ISELECT route 2 are the factored direct-load case described above.

## Current model

The three bits are consumer scheduling state associated with the live dynamic
return graph, not an opcode selector and not a permanent producer label.  In
the isolated four-return ISELECT shape, a retained prior read of the first
issued return slot changes the native consumer state from 1 to 2 while every
other ISELECT field stays fixed.  Swapping issue order moves the transition to
the new first return.  More complex prior-read sets produce states 3 and 4 and
also change producer-chain allocation.  This is consistent with a small
numbered dynamic-cache/publication network whose current route is selected by
the compiler from the scheduled dataflow.

Still unresolved is the general state-transition algorithm: how each producer
form allocates a chain, how reads retain or advance it, and whether the same
transition function applies to every route-bearing ALU form.  Those questions
should be attacked with native single-step schedule panels like this one,
followed only later by targeted bit mutations.
