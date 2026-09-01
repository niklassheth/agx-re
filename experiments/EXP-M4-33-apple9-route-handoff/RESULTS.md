# EXP-M4-33 results

## Result

The earlier EXP-M4-30/31 interpretation was too stateful.  A prior read is not
merely an invisible event that advances a global route cursor.  When the prior
reader is itself a decoded route-bearing instruction, Metal explicitly routes
its first read, and later reads of that retained value use route zero.

The smallest model consistent with the new data is:

- route zero selects the ordinary/materialized GPR path;
- a nonzero value selects transient producer-return/publication state;
- after the first route-bearing consumer reads and retains a transient value,
  subsequent reads of that same value use route zero; and
- a later multi-source instruction's nonzero route can therefore belong to the
  other source that has not yet been materialized.

This is a much simpler per-value handoff than the prior "recently read return
slot changes a global cursor" description.  The exact numbering of nonzero
routes and its encoding in integer-ALU forms remain unresolved.

## Native handoff panel

Each program has two asynchronous float returns.  A `falu2i` first reads and
retains either `p0` or `p1`; a binary `falu2` then combines the original two
returns.  The decoded instruction order, not MSL statement order, qualifies
the case.

| Producer | Return read first | Producer issue order | Prior `falu2i` route | Later binary route |
|---|---:|---:|---:|---:|
| texture | p0 | p0,p1 | 1 | 2 |
| texture | p1 | p0,p1 | 1 | 2 |
| texture | p0 | p1,p0 | 1 | 2 |
| texture | p1 | p1,p0 | 1 | 2 |
| atomic return | p0 | p0,p1 | 6 | 1 |
| atomic return | p1 | p0,p1 | 6 | 1 |
| atomic return | p0 | p1,p0 | 6 | 1 |
| atomic return | p1 | p1,p0 | 6 | 1 |

The prior instruction has `opflags=0`, retaining its source.  The final binary
instruction has `opflags=3`, releasing both sources.  Moving the first read
between operands or swapping producer issue order changes register assignment
but not either route.

The three-read arm is more decisive:

| Producer | Three retained reads of p0 | Final p0+p1 route |
|---|---:|---:|
| texture | 1, 0, 0 | 2 |
| atomic return | 6, 0, 0 | 1 |

All three prior instructions read the same encoded source register.  Only the
first read uses the producer's transient route; the second and third use route
zero.  The final binary instruction still has a nonzero route while combining
that materialized value with the other, never-previously-consumed return.  This
is the strongest current evidence that the explicit route selects an
exceptional/transient source path, while zero is the ordinary GPR path.

Validation:

- 10 semantic cases and two equivalent formulations each.
- 20 native cases compiled in forward and reverse fresh-process order.
- 40/40 complete 4-KiB hardware outputs exact.
- 10/10 formulation pairs have byte-identical stage mains.
- Every case contains the requested prior `falu2i` sequence before exactly one
  binary `falu2` target.

The complete instructions and route fields are in `NATIVE_CENSUS.json`.

## The old IMAD panel was confounded

EXP-M4-30's strongest native pair used a preceding IMAD.  Reading p0 versus p1
changed two IMAD bytes together:

```text
p0: 9f 10 54 00 02 04 32 00 d0 24 02 00
p1: 9f 20 54 00 02 08 32 00 d0 24 02 00
       ^^          ^^
```

The original analysis treated the IMAD as a known read and attributed the
following ISELECT route transition to hidden machine state.  A 2x2 hardware
cross now separates those bytes while leaving the following native route-2
ISELECT unchanged:

| IMAD mutation | Full output | Separately stored IMAD value | Following ISELECT output |
|---|---|---|---|
| none | exact | p0 | exact |
| byte 1: `0x10 -> 0x20` | exact | p0 | exact |
| byte 5: `0x04 -> 0x08` | expected controlled change | p1 | exact |
| both | identical to byte-5-only | p1 | exact |

Each cell was repeated in a fresh process with byte-identical output.  The
byte-5 variants differ from the native oracle only in bytes 1024..2047, the
separate prior-IMAD store, and match an independent p1-times-original-constant
oracle exactly.  The first 1024 bytes containing the ISELECT result remain
exact.

Therefore:

- IMAD byte 5 is the source selector in this carrier.
- The co-varying byte-1 field is inert here; it is not evidence of an IMAD
  route selector.
- Keeping ISELECT route 2 while changing the actual preceding read from p0 to
  p1 is hardware-correct.  Route 2 is not semantically defined as "p0 was just
  read."

This supersedes EXP-M4-30's causal wording.  Its native compiler correlation
remains real, but it did not identify the hardware transition rule.
`IMAD_CROSS_RESULTS.json` contains the exact hashes, changed ranges, statuses,
and repetition checks.

## Route 6 is not atomic-specific in the public corpus

The EXP-M4-32 public-corpus assembly was recounted by whether each unique
program contains a decoded `atomic_mem`, `atomic_rmw`, or `atomic_tg`.  Basic
route-bearing `falu2`/`falu2i` instructions were counted only when their local
descriptor identifies add/multiply `opsel` 4 or 5.

Across all 30,560 locally tokenized unique programs:

| Program class | Programs | Route 0 | Route 1--5 | Route 6 |
|---|---:|---:|---:|---:|
| contains a decoded atomic | 49 | 62 | 0 | 2 |
| no decoded atomic | 30,511 | 27,084 | 563 | 1,464 |

Atomic-containing programs therefore supply only 2/1,466 route-6 instances.
Route 6 is 3.1% of their basic route-bearing instructions, versus 5.0% in the
non-atomic programs.  It is not enriched in the atomic group.

The fully descriptor-complete subset gives the same qualitative result but is
small: 11 atomic programs contain six route-0 instructions and one route-6
instruction; 3,609 non-atomic programs contain 342 route-6 instructions.

Neither of the two atomic-program route-6 instructions consumes an atomic
return.  Both precede the program's atomic instruction and immediately follow
device loads:

| Program | Route-6 FALU | Nearby device load(s) | Atomic |
|---|---:|---:|---:|
| `embedding_bag_per_sample_weights_backward_float_int` | `0x1f6` | `0x1ce`, `0x1dc` | `0x1fc` |
| `embedding_bag_backward_float_int` | `0x23e` | `0x230` | `0x262` |

Thus the controlled atomic-return route 6 is a particular allocation in that
small schedule, not an atomic producer tag.  The public route-6 population is
overwhelmingly associated with other outstanding state, especially device
loads.  `ATOMIC_ROUTE6_CENSUS.json` preserves the exact counts and witnesses.

## Why route 6 dominates

Route 6 is positional in the fully decoded public corpus.  It behaves like the
preferred/default transient return slot, not the sixth allocation after routes
1 through 5.

Of the 296 unique programs with any nonzero basic `falu2`/`falu2i` route:

- 250 (84.5%) use route 6 as their first nonzero route;
- 220 (74.3%) use route 6 and no other nonzero route; and
- only 46 begin with route 1 or 2.

Segmenting the instruction stream at each new device load is even stronger.
The first nonzero basic consumer following the latest load is route 6 in
333/391 segments.  When that consumer is immediately after a consecutive run
of loads, the distribution is:

| Consecutive loads | route 1 | route 2 | route 6 |
|---:|---:|---:|---:|
| 1 | 5 | 1 | 113 |
| 2 | 2 | 0 | 82 |
| 3 | 0 | 0 | 8 |
| 4 | 0 | 0 | 4 |
| 7 | 0 | 0 | 2 |

Thus 209/217 immediate nonzero post-load consumers use route 6.  Lower-frequency
routes then appear as overlap grows: every route-3, route-4, and route-5
instance occurs in a program with an earlier route 6.  Two independently
compiled GEMV bodies contain the complete ordered explicit sequence
`6,1,2,3,4,5` after issuing their load batch.  Other high-pressure programs
consume the same set in a different order, as expected when allocation order
and consumer order differ.

The two live physical interpretations are therefore narrow:

1. route 6 is the preferred first entry in a reusable six-entry pool whose
   remaining allocation order is 1, 2, 3, 4, 5; or
2. route 6 names a distinguished direct-return/bypass path, while routes 1--5
   name overflow/cache entries.

Repeated isolated load/consume groups return to route 6, so either model needs
preferred reuse after release.  In the 24/24 fully decoded pairs where a
route-6 basic FALU has `opflags=3` (both sources released), at least one new
device load intervenes, and another nonzero basic FALU follows, the later route
is 6 again.  This favors a preferred reusable entry/free-list head over a
monotonically advancing counter.  The corpus still cannot distinguish a
special pool entry from a physically distinct bypass.  Texture results also
show that this is not a universal numbering recipe: the controlled
two-texture-return carrier uses routes 1 then 2, while the two-atomic-return
carrier uses 6 then 1.  A compiler must preserve the token chosen by the
producer schedule rather than derive a route from producer kind or source
register alone.

`ROUTE6_POSITION_CENSUS.json` records the position and sequence counts.

## Current compiler model

The useful provisional model for Mesa is per value, not a global provenance
matrix or a recent-read cursor:

1. An asynchronous producer can leave a value on a transient publication path
   associated with its GPR destination.
2. A route-bearing consumer uses a nonzero selector when consuming that
   transient form.
3. If the source remains live, later reads use the ordinary GPR route zero.
4. Source release/last-use controls are separate from the route selector.
5. If an instruction family cannot directly name the transient path, the
   compiler must materialize first or use that family's still-undecoded
   equivalent.

Still open:

- Which source operand owns the single route field in every multi-source form.
- How nonzero route numbers are allocated across producer mechanisms and
  instruction families.
- Whether every nonzero value is merely an interchangeable bypass selection in
  low-pressure carriers or becomes required under high occupancy.
- IMAD's complete source/lifetime encoding; its current `b1hi` field must not
  be promoted to a route based on this evidence.

The next discriminating experiment should hold one transient source and one
materialized source fixed while swapping operand roles in a simple binary
instruction, then repeat under enough outstanding-return pressure that route
mutations are sensitivity-positive.  It should not return to an unconstrained
producer/consumer matrix.
