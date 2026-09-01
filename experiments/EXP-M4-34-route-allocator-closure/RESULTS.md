# EXP-M4-34 results

## Result

The nonzero Apple9 route is a required selector for a transient return slot.
Device loads and texture operations use one shared six-slot set, but begin
their free-slot search at different places:

```text
device load: 6, 1, 2, 3, 4, 5
texture:     1, 2, 3, 4, 5, 6
```

The producer instruction claims the first free slot in its order.  A compiler
can simulate that allocator over the decoded machine-instruction issue order.
This accounts for the previously surprising route-6 dominance and texture's
route-1 start without inventing two kinds of ALU route.

All statements below are qualified from the generated instructions, not MSL
statement order.  The evidence is 50 byte-stable native cases, 100/100 exact
native hardware executions, 46 focused route-mutation executions, and 12
lifetime-mutation executions on T8132/macOS 26.6.2 build 25G83.  Every check
uses the complete 4-KiB output oracle.  `RESULTS.json` contains every decoded
instruction and exact result signature.

## Shared allocator and texture's initial slot

Homogeneous batches establish the two search orders directly:

| Pending returns | Routes used by their first consumers |
|---|---|
| 1--5 device loads | `6`; `6,1`; `6,1,2`; `6,1,2,3,4` |
| 1--5 textures | `1`; `1,2`; `1,2,3`; `1,2,3,4,5` |

The mixed triples prove that the two producers share slots and skip each
other's allocations:

| Logical values | First-consumer routes |
|---|---|
| load, load, texture | `6,2,1` |
| load, texture, load | `6,1,2` |
| texture, load, load | `1,6,2` |
| texture, texture, load | `1,2,6` |
| texture, load, texture | `1,6,2` |
| load, texture, texture | `6,1,2` |

For example, in load/load/texture the texture is actually issued first and
claims slot 1.  The two later loads claim 6 and then skip occupied 1 to claim
2.  The consumers therefore read `6,2,1`.  The reverse-order, fresh-process
compile produces the same stage main.

The smallest useful interpretation is producer-specific free-list heads over
one shared set.  Whether hardware implements a literal scanned bitmap, linked
free list, or equivalent scoreboard is not distinguished and does not need to
be exposed by the compiler.

## Reuse, holes, and retained values

First consumption transfers a pending value into the ordinary GPR path when
the value remains live.  Subsequent reads use route 0.  This is independent of
return-slot reuse:

| Case | Routed reads |
|---|---|
| one load read three times | `6,0,0` |
| one texture read three times | `1,0,0` |
| retained load, new dependent load, old load again | `6,6,0` |
| retained texture, new dependent texture, old texture again | `1,1,0` |

Thus the transient slot becomes reusable at the first routed handoff even
when the logical value remains live in a GPR.  A later producer may immediately
reuse that slot; the retained old value is addressed through route 0.

The load gap case issues three loads into `6,1,2`, consumes/relinquishes 6,
then issues another load while 1 and 2 remain pending.  Its consumers are
`6,1,2,6`: the new value reused the freed preferred slot 6.  A second case
frees 6 and 1 while slot 2 remains occupied, then issues two new loads.  Metal
uses 6 and 1 again; the old slot-2 value and the new pair both execute exactly.

The analogous texture formulation frees 1 and 2 and then emits three texture
operations, which use 1, 2, and 3.  Metal scheduled away the attempted
single-interior-hole texture form, so there is not a native claim here that an
arbitrary noncontiguous pending tuple is directly consumable.  The allocator's
collision skipping is independently established by all six mixed triples.

## Retain and release edge checks

The first routed consumer in each sequential case has the source-release bit
clear.  The old value later reads correctly through route 0 even though a new
producer has reused route 6 or 1.

Changing only that source-release bit from clear to set has the same exact
signature for loads and textures, twice each:

- the first routed result stays correct;
- the intervening new load or texture stays correct;
- all 64 lanes of the later old-value read become zero; and
- no other output word changes.

This establishes that source release is real lifetime state and is separate
from the transient route-slot handoff.  It is not a scheduler hint.

Clearing the neighboring destination-publication bit in this particular
carrier was an exact null twice for both producer kinds.  That is deliberately
recorded as a carrier-local result, not a reclassification of the field: the
value has a short dependent forwarding path here, and older independent
experiments make the bit load-bearing in other schedules.

## Multiple pending sources

Direct multi-pending consumption is legal.  Native Metal emits, and hardware
executes exactly:

- one `falu2` consuming two pending device loads, route 6;
- one `falu2` consuming two pending textures, route 1;
- one `falu2` consuming one load and one texture in either operand order,
  route 6;
- one `falu3` consuming three pending loads, route 6;
- one `falu3` consuming three pending textures, route 1; and
- one `falu3` consuming load/texture/load, route 6.

The single route field names the base of the pending-return group.  Operand
descriptors/register fields identify the values within it.  The `6,1` wrap is
ordinary: a load+texture binary consumer uses route 6, not a second route
field.

This is not merely a native correlation.  Seven exact control archives and
16 route-only alternatives were each executed twice.  Every native route was
exact.  Every route-0 or plausible neighboring-route mutation made all 64
result lanes zero and changed no other word.  The native group base is therefore
required hardware state.

The tested n-ary cases use allocator-contiguous groups, including the `6 -> 1`
wrap.  Metal consistently schedules or materializes intermediate values so
the tested consumers do not need an arbitrary group containing an unfilled
interior hole.  Mesa should initially do the same; direct noncontiguous-tuple
encoding remains outside this closure rather than being guessed.

## Compiler rule

A basic Apple9 compiler can use this state machine:

1. Track free transient slots `{1,2,3,4,5,6}` over final instruction order.
2. On a device load, allocate the first free slot in `6,1,2,3,4,5`.
3. On a texture operation, allocate the first free slot in `1,2,3,4,5,6`.
4. Preserve the assigned slot with the pending SSA value.
5. On its first capable consumer, emit the required nonzero route.  For an
   n-source pending group, emit the group's base route and the native operand
   descriptors.
6. If the SSA value stays live, retain/materialize it; subsequent reads use
   route 0.  Otherwise set the appropriate source-release bit.
7. Return the transient slot to the free set at the routed handoff.  GPR
   liveness continues separately.
8. If pending operands cannot be represented as a proven contiguous group,
   materialize enough operands first instead of inventing an encoding.

This is sufficient for the basic load, texture, binary FALU, and three-source
FMA schedules tested here.  Route 7 and broad producer families are explicitly
outside this experiment.

## Mesa implication

The current integration compiler does not yet implement this model.
`agx_apple9_assign_vir_consumer_routes()` classifies device-load values as
capture-derived `DEVICE_LOAD_00`/`DEVICE_LOAD_11` producer kinds and maps those
classes directly to routes 1/6.  It has no shared transient-slot occupancy,
first-handoff state, texture allocation, or mixed-producer collision handling.

That classifier should be replaced, not extended with more producer classes.
The route allocator belongs after final scheduling, alongside physical-register
liveness: assign a transient slot at each asynchronous producer, transfer or
release it at the first route-capable consumer, and keep subsequent SSA uses on
the ordinary GPR path.  Capture-derived raw load framing fields remain a
separate packaging/encoding concern.
