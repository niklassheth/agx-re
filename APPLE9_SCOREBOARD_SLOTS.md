# Apple9 scoreboard slots

## Summary

Apple9 has a small set of transient scoreboard slots used to connect
asynchronous producers to the first instruction that consumes their results.
Older experiment names and notes call the consumer field a **route**.  This
document calls it a **slot selector**, because the accumulated evidence is much
more consistent with scoreboard allocation than with value provenance or a
choice between ALU datapaths.

The current compiler-facing model is:

1. An asynchronous producer publishes a result through a nonzero scoreboard
   slot.
2. The first capable consumer names that slot.  Its ordinary operand fields
   still identify the value or values being consumed.
3. Several pending producers feeding one multi-source instruction may form one
   scoreboard group.  The consumer names the group's base slot; it does not
   carry one selector per source.
4. The first slot-bearing handoff makes the scoreboard slot reusable.  If the
   logical value remains live, it is retained/materialized in the ordinary GPR
   path and later reads use slot 0.
5. Source retain/release controls are independent of the slot selector.

Slots 1 through 6 are routinely emitted.  Slot 0 means the ordinary,
non-pending GPR path.  Apparent slot-7 occurrences are extremely rare and may
be decoder artifacts: several occur in streams that are incompletely or
incorrectly tokenized around the purported slot-bearing instruction.  There is
currently no controlled evidence that slot 7 is a real scoreboard slot, so it
must not be part of the initial compiler model.

This model is established most strongly for scalar device loads, texture
operations, device atomic returns, and basic floating-point consumers.
Several other load and stage-specific producer forms remain open.

## Evidence boundary

All controlled programs discussed here were compiled from our own MSL.  No
Apple binary was disassembled or decompiled.  The primary environment was a
T8132 M4 Mac mini running macOS 26.6.2 build 25G83.

The allocator closure consists of 50 byte-stable native programs, 100/100
exact native hardware executions, 46 focused consumer-slot mutations, and 12
lifetime mutations.  Every hardware result was checked against the complete
4-KiB output oracle, rather than merely checking retirement or a counter.

The main evidence sets are:

- [`EXP-M4-33-apple9-route-handoff`](experiments/EXP-M4-33-apple9-route-handoff/RESULTS.md): first handoff, retention, reuse, and the original slot-6 census.
- [`EXP-M4-34-route-allocator-closure`](experiments/EXP-M4-34-route-allocator-closure/RESULTS.md): the shared six-slot allocator, gaps, reuse, and multi-source consumers.
- [`EXP-M4-35-native-load-xor`](experiments/EXP-M4-35-native-load-xor/RESULTS.md): integer logic's direct pending-load handoff and six-bit one-hot slot mask.
- [`EXP-M4-49-atomic-publication`](experiments/EXP-M4-49-atomic-publication/RESULTS.md): six-bit atomic-result destinations and all six atomic publication slots on hardware.
- [`EXP-M4-50-atomic-input-dependency`](experiments/EXP-M4-50-atomic-input-dependency/RESULTS.md): the atomic packet's six-bit input dependency mask, all six producer slots, and removal of the bogus Mesa atomic-prep pseudo.
- [`EXP-M4-51-compact-0b`](experiments/EXP-M4-51-compact-0b/RESULTS.md): prep-free pending-load-to-returning-atomic execution for every coherent input/result slot pair.
- [`EXP-M4-30-apple9-route-semantics`](experiments/EXP-M4-30-apple9-route-semantics/NATIVE_CENSUS.json): controlled ISELECT schedules, including atomic-return allocation changes.
- [`EXP-M4-32-public-metal-corpus`](experiments/EXP-M4-32-public-metal-corpus/CORPUS_CENSUS.json): distributional checks against a much larger native-Metal corpus.

## Terminology

| Term | Meaning in this document |
|---|---|
| slot 0 | Ordinary/materialized GPR path; no pending scoreboard handoff. |
| slots 1--6 | Reusable transient scoreboard slots emitted by native Metal. |
| producer tag | Producer-side bits describing the scoreboard publication/group. |
| consumer slot | The nonzero selector on a capable consuming instruction. |
| scoreboard group | One or more pending results consumed together through one base selector. |
| first handoff | The first slot-bearing read of a pending result. |
| retained value | A value copied/kept in the GPR path after first handoff for later slot-0 reads. |

Calling these *slots* does not claim a particular transistor-level
implementation.  Hardware might implement a bitmap, linked free list, token
queue, or an equivalent dependency scoreboard.  Multi-source sharing makes
"scoreboard slot" a better abstraction than "return-value storage slot": a
single slot can govern a group containing multiple distinct result values.

## The six-slot allocator

Scalar device loads and texture operations use the same six-slot pool but start
their searches at different places:

```text
scalar device load: 6, 1, 2, 3, 4, 5
texture operation:   1, 2, 3, 4, 5, 6
```

For separately consumed pending results, homogeneous native batches produce:

| Pending returns | Slots on their first consumers |
|---|---|
| 1--5 scalar device loads | `6`; `6,1`; `6,1,2`; `6,1,2,3,4` |
| 1--5 textures | `1`; `1,2`; `1,2,3`; `1,2,3,4,5` |

Mixed batches show that the two producer families share one pool and skip
occupied slots:

| Logical values | First-consumer slots |
|---|---|
| load, load, texture | `6,2,1` |
| load, texture, load | `6,1,2` |
| texture, load, load | `1,6,2` |
| texture, texture, load | `1,2,6` |
| texture, load, texture | `1,6,2` |
| load, texture, texture | `6,1,2` |

These results are based on decoded machine-instruction issue order, not MSL
statement order.  Metal often reorders the producers.

### Why slot 6 is common

Slot 6 is the preferred first slot for the dominant scalar-load path.  It is
not an "atomic result class" and it is not the sixth allocation after slots
1--5.

In the public corpus, 250 of 296 programs containing a nonzero basic FALU slot
begin with slot 6, and 220 use no other nonzero slot.  Lower-numbered slots
become visible as pending lifetimes overlap.  Repeated isolated load/consume
groups return to slot 6 after the preceding handoff.

Texture operations instead prefer slot 1.  The different starting points are
compiler scheduling/allocation policy over one shared pool, not evidence for
two different kinds of consumer slot field.

## Producer-side encodings

### Scalar device loads

For the controlled scalar `device_load` form, the producer's scoreboard tag is
split across byte 8 bits 7:6 and byte 9 bit 0.  The complete observed two-byte
tokens are:

| Slot | Bytes 8--9 |
|---:|---:|
| 1 | `11 00` |
| 2 | `51 00` |
| 3 | `91 00` |
| 4 | `d1 00` |
| 5 | `11 01` |
| 6 | `51 01` |

If `s` is the slot number and

```text
t = (2 * (s - 1)) mod 7
```

then the variable bits are:

```text
byte8[7:6] = t >> 1
byte9[0]   = t & 1
```

The remaining bits in these bytes belong to other load-result framing and
destination fields.

This is not merely a consumer-side inference.  The producer token changes with
the slot assigned by native Metal.  In a binary FALU consuming two pending
scalar loads, both loads carry `51 01` and the FALU selects slot 6.  The two
values remain distinct through the normal operand/result descriptors.  This is
the clearest evidence that the selector describes a scoreboard group rather
than storage for exactly one value.

The formula is proven only for this scalar load form.  Apple9 has several other
load encodings.  Vector, constant, threadgroup, and other formatted loads may
place or interpret the publication bits differently.  The old
`DEVICE_LOAD_00`/`DEVICE_LOAD_11` producer-class scheme confuses raw packaging
bits with scheduling state and should not be extended.

### Device atomic returns

Returning device atomics are followed by an eight-byte result-publication
record.  Its destination is a six-bit register field spanning byte 0's high
nibble and byte 2 bits 7:6.  Every destination `r0..r63` passed exact hardware
testing.

The record's byte 5 bits 7:5 select the scoreboard slot using a compact code:

| Slot | Publication code | Byte 5 |
|---:|---:|---:|
| 6 | `001` | `0x20` |
| 1 | `010` | `0x40` |
| 2 | `100` | `0x80` |
| 3 | `011` | `0x60` |
| 4 | `101` | `0xa0` |
| 5 | `110` | `0xc0` |

Native own-source Metal establishes the first three encodings.  EXP-M4-49
establishes all six on hardware with six simultaneously pending returned
atomics and distinguishable exact output oracles.  Code `111` remains
unassigned and is not evidence for a seventh slot.

An earlier interpretation placed the returned-result slot in the atomic
packet's bits 12--17 because native packet byte 1 values correlated with later
consumer schedules.  Coordinated hardware tests refute that interpretation:
changing those six bits as an output-slot selector broke result publication,
whereas changing the adjacent result record was exact.

EXP-M4-50 closes the packet field as a six-bit input dependency mask:

```text
mask = ((byte1 >> 4) & 0x0f) | ((byte2 & 0x03) << 4)
```

All six one-hot producer dependencies were required and sufficient in
controlled direct-load-to-atomic tests. Ordinary materialized inputs use mask
zero. Thus `67 01 56` is not a separate direct form: it is the common `0x54`
packet with the slot-6 dependency bit embedded in byte 2.

Native Metal may place compact `0b 00 00 02` or a ten-byte low-`b` record
before a returned atomic.  Neither is a required ownership-transfer operation.
EXP-M4-51 removed all six such records from a carrier with six simultaneously
pending loads and six returned atomics, then passed all 36 input-slot/result-slot
permutations in both forward and reverse execution order.  This includes every
same-slot handoff.  The compact record is correlated with Metal's slot-1 input
schedule, while the ten-byte encoding is part of a much broader instruction
family.  Their exact scheduling or cache effect remains unresolved, and the
compiler should not model either as a mandatory atomic-prep pseudo.

### Texture and image reads

Texture reads use the same logical slot pool, but their companion/result bundle
is more structured than the scalar load token.  In separately consumed scalar
texture chains, the companion fields co-vary with slots 1--5 as follows:

| Consumer slot | `comp_flags` | `result_desc & 1` |
|---:|---:|---:|
| 1 | `0` | `0` |
| 2 | `2` | `0` |
| 3 | `4` | `0` |
| 4 | `6` | `0` |
| 5 | `0` | `1` |

This follows the same `t = 2*(s-1) mod 7` sequence visible in scalar loads.
However, the texture bundle also describes result layout and member placement.
For example, two or three pending textures consumed by one FALU have companion
sequences `0,2` or `0,2,4`, while the consumer names the group base, slot 1.

Therefore it is premature to label either texture field as a standalone slot
selector.  The bundle demonstrably carries allocation/member information, but
the exact split among group base, member position, result register, and
component selection still needs coordinated producer-field mutations.  A
controlled texture allocation reaching slot 6 is especially useful: the
sequence predicts `comp_flags=2` with the odd-half bit set, but that encoding
is not yet established.

Texture samples, reads, gathers, and image reads share related hardware
machinery, but only the controlled scalar texture-read/sample cases are part of
this closure.

## Consumer-side slot selectors

The strongest consumer-side closure is for basic `falu2`, `falu2i`, and the
tested `falu3` form.  A nonzero field selects the scoreboard slot or the base
of a contiguous pending-result group.  The register and operand descriptors
still select individual values.

Hardware mutations establish that this field is required state:

- the unmodified native selector produces the exact output;
- changing it to slot 0 or a plausible neighboring slot makes every affected
  lane zero in the controlled carriers; and
- unrelated output words remain unchanged.

Similar-looking fields exist in ISELECT and other ALU encodings.  Native data
strongly suggests a common scoreboard concept, but each instruction form still
needs its field location, source roles, and release controls verified.  An
ISELECT carrier in which all selector mutations were exact demonstrates why a
field-looking-alike is not sufficient evidence by itself: the generated data
flow must prove that the mutated selector actually governs a pending operand.

The extended integer-logic (`ilogic`) family uses the same logical scoreboard
slots but a different physical encoding from basic FALU.  Its six slots are a
one-hot mask:

| Slot | `ilogic` instruction bit |
|---:|---:|
| 1 | 45 |
| 2 | 46 |
| 3 | 47 |
| 4 | 61 |
| 5 | 62 |
| 6 | 63 |

Slot 0 clears all six bits.  The field location is part of the common extended
`ilogic` form; AND, OR, and XOR select their truth-table operation through
separate opcode bits.  The compiler therefore applies this slot encoding to
all three operations rather than treating XOR as a special consumer.

The direct native and hardware closure was performed with XOR.  A native
six-load XOR chain occupies slots
`6,1,2,3,4,5` and emits masks `0x20,0x01,0x02,0x04,0x08,0x10`, with exact
full-buffer results.  Two pending loads consumed by one XOR share one slot-6
producer tag and one bit-63 consumer mask; the logic operand descriptors still
identify both values.

This distinction is essential for a compiler.  Treating bits 45--47 as the
same binary field used by FALU turns binary slot 6 into the masks for slots 2
and 3 and produces zero results.  The temporary `UMIN(x, x)` materialization
bridge avoided that bad encoding, but native Metal consumes the pending loads
directly.  Instruction families may share allocator semantics without sharing
field representation.

## Multiple pending sources

Direct multi-source consumption is legal.  Native Metal emits and T8132
executes correctly:

- one FALU2 consuming two pending scalar device loads, base slot 6;
- one FALU2 consuming two pending textures, base slot 1;
- one FALU2 consuming a load and texture in either operand order, base slot 6;
- one FALU3 consuming three pending loads, base slot 6;
- one FALU3 consuming three pending textures, base slot 1; and
- one FALU3 consuming load/texture/load, base slot 6.

The `6 -> 1` wrap is ordinary.  A load-plus-texture consumer still has only one
slot field and uses base slot 6.  Operand descriptors identify the members of
the group.

Sixteen neighboring-slot mutations across the reviewed multi-source cases were
executed twice.  Native selectors remained exact; slot 0 and neighboring
alternatives zeroed all 64 result lanes.  Thus the single group-base selector
is hardware-required state, not just compiler metadata.

The proven groups are allocator-contiguous, including the `6 -> 1` wrap.
Arbitrary pending tuples with an unfilled interior hole are not proven.  An
initial compiler should materialize enough sources to reduce such a tuple to a
known encoding instead of guessing.

### Direct pending-result device stores

The scalar `device_store` form with address mode `0x56` is a different kind of
consumer.  It has no separately encoded scoreboard-slot selector.  Controlled
two-load programs show that store byte 3 names the pending result by its
destination half-register/GPR:

- Loads A→r0/slot6 and B→r1/slot1 can be stored as A,B or B,A solely by
  changing the two stores from r0,r1 to r1,r0.
- Reversing producer issue order while preserving those associations remains
  exact.
- Swapping the slot-6 and slot-1 producer tags independently of issue order
  remains exact; values still follow r0/r1.
- A slot6+slot2 pair also stores in either order, proving an interior slot-1
  hole is legal for this direct-store schedule.
- The first store does not invalidate the other pending value: both store
  orders complete exactly.

There is nevertheless a scalar-load head constraint.  An isolated slot-6
load stores correctly, whereas an otherwise identical isolated load tagged
slot 1 or 2 stores zero.  Those same slot-1/2 tags work when the pending set
also contains a slot-6 scalar load, even if the lower-numbered producer is
issued first.  This distinguishes two facts that must not be collapsed:

1. The producer set must follow the proven scalar allocation/group contract,
   currently requiring slot 6 to be present.
2. Once that set is valid, direct store selects an individual pending value by
   GPR association rather than by an explicit or implicit slot-6 selector.

This result is `EXP-M4-36-device-store-scoreboard`: 14 whole-program cases,
42/42 exact execution canaries, no faults or hangs, and full five-word
readback.  A separate high-confidence native-corpus census finds 40/40 unique
adjacent direct pairs (208 weighted occurrences) using slot 6.  Therefore the
initial compiler does **not** exploit the broader synthetic behavior: it emits
`0x56` only for a slot-6 producer and materializes slot-1--5 values first.

## First handoff, retention, and release

The scoreboard lifetime and GPR lifetime are related but distinct.

For a value read repeatedly:

| Case | Successive consumer slots |
|---|---|
| one load read three times | `6,0,0` |
| one texture read three times | `1,0,0` |
| retained load, dependent new load, old load again | `6,6,0` |
| retained texture, dependent new texture, old texture again | `1,1,0` |

The first nonzero read performs the pending handoff.  If the logical value
remains live, hardware/compiler state retains it on the ordinary GPR path and
later reads use slot 0.  The transient scoreboard slot may be reused
immediately by another producer.

Gap tests confirm free-slot reuse:

- Loads allocated as `6,1,2`; after slot 6 was handed off, a new load reused
  slot 6 while slots 1 and 2 remained pending.
- After slots 6 and 1 were handed off while slot 2 remained pending, two new
  loads reused 6 and 1.
- Texture cases similarly reused their preferred low slots after handoff.

Source release is separate.  In retained-value carriers, setting only the
source-release bit left the first pending read and the intervening new producer
correct, but changed every later read of the old value to zero.  No unrelated
output changed.  The release bit therefore controls the retained GPR lifetime;
it is not the scoreboard selector and not merely a scheduling hint.

## What is not a scoreboard producer

The earlier provenance inventory intentionally overclassified possible
producers.  Later evidence narrows it:

- Ordinary ALU and immediate values use the slot-0 GPR path unless they are
  participating in some separately proven forwarding form.
- SIMD shuffle/subgroup results were exact under all consumer-slot mutations
  in the tested carrier.  There is currently no evidence that they allocate
  one of these asynchronous scoreboard slots.
- Merely observing a nonzero field near an operation is not enough.  Native
  assembly data flow and a sensitivity-positive hardware mutation are needed
  before adding a producer to the slot allocator.

## Compiler model

Scoreboard-slot assignment belongs after final instruction scheduling, close
to physical-register liveness.  It should not be represented as a permanent
SSA provenance class.

Physical-register liveness must also cover the asynchronous return window.
A vector device load writes its complete adjacent destination tuple when its
scoreboard handoff occurs.  Every lane of that tuple therefore remains
reserved from issue through the first handoff, including lanes with no SSA
consumer.  Reusing a dead lane earlier creates two in-flight writers to the
same GPR.  This was observed directly on T8132: a pending `uint4` load into
`r17:r20` followed by a scalar load into prematurely recycled `r20` passed on
a favorable first launch but returned stale tuple data on repeated launches.
Keeping `r17:r20` reserved and placing the scalar return in `r21` made both
single-command and separately retired repeated-dispatch tests exact.  This is
a register-allocation lifetime rule, not an instruction materialization or
barrier requirement.

A conservative initial Apple9 compiler can use this procedure:

1. Identify instruction forms proven to produce pending asynchronous results.
2. Compute each result's first capable consumer after final scheduling, and
   reserve its complete physical destination tuple through that handoff.
3. Form only proven multi-source groups.  Initially require the native
   contiguous/wrapping shapes already observed.
4. Allocate a free slot using the producer family's observed preference:
   scalar loads begin at 6; textures begin at 1.
5. Encode the producer publication/group tag and any member descriptors.
6. Encode the consumer handoff using that instruction family's representation:
   basic FALU uses a binary base-slot selector, extended `ilogic` uses the
   six-bit one-hot mask above, and the direct scalar store is admitted only for
   a slot-6 producer while using its source half-register/GPR association.
7. At first handoff, return the transient slot to the free set.
8. If the SSA value remains live, retain/materialize it and make later uses
   slot-0 GPR reads.  Otherwise emit the proven last-use/release controls.
9. When a tuple or producer form is not yet representable, materialize or
   reschedule rather than inventing a selector.

Atomic results may use slots 1--6, but their allocation must follow issue order
and pending lifetimes.  An isolated first return uses preferred slot 6; merely
forcing that return to a different free-looking slot is not a valid schedule.
The old Mesa logic that maps `DEVICE_LOAD_00`/`DEVICE_LOAD_11` classes directly
to fixed selectors should be replaced by scheduled scoreboard allocation, not
expanded with more producer-class cases.

## Open questions

The following are intentionally unresolved:

1. **Slot 7.** Apparent corpus occurrences are extremely rare and may be
   decoder artifacts.  The known candidates are concentrated in streams that
   are incompletely or incorrectly decoded around the purported slot-bearing
   instruction, and some are likely different instruction forms mistaken for
   slot-7 FALU records.  No controlled native-Metal or hardware experiment has
   established that slot 7 exists.  It must not be emitted unless new evidence
   first distinguishes a genuine slot from decoder desynchronization.
2. **Other load forms.** Vector, constant, threadgroup, and differently
   formatted device loads do not all expose the scalar token in the same
   place.  The capture-derived `00/01/10/11` distinctions need semantic
   decoding rather than producer classes.
3. **Other atomic forms.** Returning threadgroup atomics and the threadgroup
   input dependency encoding still need controlled captures and mutations.
   Per-lane device atomic input dependencies, return destinations, and
   publication slots 1--6 are closed.
4. **Texture field split.** The exact division among scoreboard group,
   member position, component selection, and return-register description is
   not yet closed, particularly at slot 6.
5. **Stage-specific producers.** Fragment iterators, tile/attachment reads,
   and other stage-only operations have not been admitted to the common slot
   model.
6. **Arbitrary multi-source shapes.** Only contiguous groups and the `6 -> 1`
   wrap are proven.  Interior holes and multiple independent pending groups on
   one consumer remain open.
7. **Hardware implementation.** The evidence establishes software-visible
   allocation and lifetime semantics, not whether the physical mechanism is a
   literal six-entry scoreboard or an equivalent token structure.

## Practical conclusions

- Call the field a **scoreboard slot**, not a provenance route.
- Treat slot 0 as the ordinary GPR path and slots 1--6 as transient pending
  handoffs.
- Allocate slots from final machine-instruction order and liveness.
- Preserve separate producer tags, consumer selectors, operand descriptors,
  and retain/release state; none substitutes for another.
- Encode extended `ilogic` slots as a one-hot mask for AND, OR, and XOR; never
  write the binary FALU selector into bits 45--47.
- For direct scalar load-to-store schedules, emit `0x56` only for a slot-6
  producer and name the pending value with the store's source half-register/GPR
  field.  Materialize slot-1--5 values rather than exploiting synthetic-only
  behavior, and do not invent a store slot selector.
- Support the proven scalar-load, texture, and contiguous multi-source cases
  first.
- Keep uncertain producer forms conservative and materialize when necessary.
- Keep the atomic packet's input-dependency bits distinct from the adjacent
  result record's destination and publication-slot fields.
- Encode ordinary/materialized device-atomic inputs with dependency mask zero.
  A directly pending input must name its actual producer slot; do not add an
  idle-slot wait as a scheduling delay.
