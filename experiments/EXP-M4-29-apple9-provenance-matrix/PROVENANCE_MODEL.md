# Apple9 provenance model

## Status

This document is populated from the gated EXP-M4-29 matrix.  Until
`verify.py --closure` succeeds, every class and rule below is provisional.

## Model shape

An Apple9 source value is described along independent axes:

1. **Architectural backing**: GPR, uniform/preload file, stage accumulator,
   memory-return slot, or another stage-specific source domain.
2. **Publication state**: the producer-side state/token which makes that value
   visible to a compatible consumer form.
3. **Lifetime state**: whether each source must remain durably readable after
   this use, including instruction-family-specific release controls.
4. **Validity window**: whether the source is durable or must be consumed in a
   stage/cache transaction before another producer invalidates it.
5. **Consumer route**: the source-file, token, and instruction-wide route
   selected for the complete ordered producer tuple.

The compatibility function is therefore:

```text
encode(consumer form,
       ordered producer tuple,
       ordered operand roles,
       live-after mask,
       stage context)
    -> direct encoding | native normalization | refusal
```

A binary `producer kind -> route` mapping may be insufficient.  The current
schema-v4 discovery pass deliberately measures homogeneous producer tuples
first.  Ordered heterogeneous tuples remain part of the eventual model, but
are deferred until the producer classes stop merging or splitting.

## Class-formation rule

Provisional producers are split whenever one consumer, lifetime form, stage,
type, or width distinguishes them.  Component labels within one vector load
width are source variants, not separate provenance classes, unless a measured
consumer signature later disproves that merge.  Math mode is likewise a case
condition rather than a perspective-iterator producer class.  Other merges
still require identical measured signatures; similar byte layout alone is
not enough.

## Normalization policy

A normalizer is part of the model only when native Metal emits the same bridge
for two independently phrased sources and both complete programs execute
exactly.  An implementation may later use that native bridge.  EXP-M4-29 does
not authorize an invented zero-add, zero-OR, move, or spill merely because it
works in one carrier.

## Derived classes and rules

Eleven narrowly evidenced homogeneous compute-select compatibility cells are
promoted to `direct_native`.  Forty-three compute-immediate source cells and
one fragment front-facing IADD cell are `native_normalized`; the remaining
4,390 applicable cells stay unresolved.
The native census demonstrates why all stage symbols matter: a
fragment invocation-invariant buffer-fed case can publish values through its
constant program/uniform path while an indexed case contains ordinary device
loads in `_agc.main`.  Classification therefore examines `_agc.main`,
`_agc.main.constant_program`, and every other `_agc.*` symbol in both pipeline
stages; absence from `_agc.main` alone is neither a refusal nor proof that an
edge was optimized away.

The schema-v4 homogeneous coverage gate contains 157 selected single-use
cells spanning every emitted stage/consumer and stage/producer target.  All
157 independently phrased A/B pairs produce identical `_agc.main` hashes and
execute exactly in both compilation orders.  Across those archives the census
extracts 1,044 `_agc.*` symbols and 21,620 instructions without error.  This
qualifies the two formulations for stable-bridge comparisons, but does not by
itself establish that an observed edge is direct.

`fragment_inverse_w_f32` is retained separately from
`perspective_iter_f32`.  The former is the rasterizer's interpolated 1/clip-W
denominator exposed as `[[position]].w`; the latter is a perspective varying
after numerator/denominator normalization.  Exact direct stores of both values
under the W=(1,2,2) geometry profile distinguish their semantics.  Whether
they ultimately share an architectural source domain remains an encoding
question for the census and ablations, not a reason to merge their semantic
producer classes prematurely.

The class-equivalence panel identified a conservative architectural merge:
for `u32`, `f32`, `u16`, `f16`, and `u64`, the `constant_*` and `device_*`
source spellings use identical load and terminal-store instruction records in
the common ALU/store panel in compute, vertex, and fragment.  Their address
construction differs, as expected.  The distinguishing panel passes 400/400
in both orders.  Most matched conditions have identical
instruction families; the remaining differences are confined to select+fanout
address scheduling and dependent-index register/address selection.  Because
those fields move together under ordinary register allocation, neither byte
identity nor byte difference alone identifies the publication class.

A paired compute `fselect` ablation supplies the missing behavioral witness.
For both source address spaces, native state 11/route 6 is exact, changing only
the select route to 1 corrupts output, changing the two selected-value load
states to 00 under route 6 remains exact, and state 00/route 1 restores exact
output.  Each arm repeats identically.  `PROVENANCE_GROUPS.json` therefore
maps dynamic `constant_*` and `device_*` scalar source spellings to the same
type-specific `buffer_load_*` architectural group.  Both spellings remain in
the corpus as construction variants; fragment-uniform publication and vector
load encodings remain separately represented.

Scalar values selected from scalar, `uint2`, and `uint4` loads also share
`buffer_load_u32` provenance.  A 204-case panel is exact in both orders, all
68 scalar-to-vector comparisons preserve the coupled producer-state sequence,
and all terminal stores match.  The paired ISELECT ablation repeats the same
route-sensitive signature for all three widths.  Element format and component
offset remain required load-construction fields; they do not create three
scalar result classes.

Ordinary integer ALU results, materialized comparison predicates, and raw
compute/vertex system indices remain separate provisional classes.  Their
176-case bounded panel is exact and order-stable, but does not expose a common
consumer signature: 21 matched conditions have distinct consumer-family
bytes, and another 34 omit an expected family on one or both sides.  A missing
family may be folding, scheduling, or an incomplete mnemonic model; it is not
evidence of normalization.  In particular, a comparison result is constrained
to zero/one while an ordinary ALU result is not, and a homogeneous system-index
select can collapse semantically.  The focused raw-index probe below removes
the latter ambiguity; a range-controlled predicate/ALU comparison is still
needed before that split can be reconsidered.

The ALU/predicate split now has a hardware route signature.  In the
fanout-live1 ISELECT form, native ALU route 2 and alternate route 7 are stably
exact in the collected repetitions; every other route has an intermittent
wrong-output witness, often restricted to one 32-lane SIMD group.  The
materialized-predicate form is exact under all eight route values in the same
bounded census.  Both selected-register positive controls change output.
Consequently these are direct native relationships but not one merged producer
class or one universal select route.

That split is not a universal property of the MSL words “ALU” and “predicate.”
A range-controlled supplement makes a shift/mask expression and a boolean
materialization produce identical runtime 0/1 values.  Across ISELECT, raw
buffer index, U2F, and branch consumers in single-use and fanout forms, seven
of eight conditions compile every source form to the same complete program;
the remaining branch-fanout condition still has one predicate spelling that
matches both ALU spellings.  The shared ISELECT is exact at all eight route
values for 14 repetitions per route and remains selected-register sensitive,
matching the materialized-predicate signature rather than unconstrained ALU.
The architectural inventory therefore needs a provisional
`bit_extract_u32`/range-constrained result class in its next schema.  Both ALU
and predicate source spellings may normalize into it; the existing full-width
`alu_u32` and comparison-derived `predicate_u32` captures remain distinct.

The raw compute system-index split now has a direct address-consumer witness.
A supplemental source uses `thread_position_in_grid` as an unmasked
constant-buffer index, with every dispatched index in bounds by construction.
Both source formulations and both compilation orders produce the same exact
result and native binary.  The native chain is `get_sr` directly into
`device_load(index_reg=1, space=16)`; an ALU-derived index uses the structurally
different `index_reg=128, space=0` load form.  Changing only the direct load's
selected address register changes full output repeatably.  This removes the
earlier ambiguity caused by the canonical safety mask: `system_index_u32` is a
real direct producer signature, not merely an integer value reconstructed by
ALU code.

Immediate source forms are not merged with runtime ALU results.  In the
bounded compute panel, Metal evaluates 35 of 43 literal relationships at
compile time and emits an exact per-cell result program; the eight
relationships whose atomic or texture side effects must remain use explicit
literal materialization before the retained consumer.  Hexadecimal and decimal
source spellings normalize to byte-identical programs in both compilation
orders.  Each retained consumer family has one pre-consumer materialization
signature across all measured lifetimes.  Integer prefix mutations are
output-sensitive.  The float compact prefix is proven non-payload, while a
coherent two-word payload recode reproduces an independently compiled native
alternate-literal oracle exactly.  These 43 cells are consequently
`native_normalized`.  This is a source-language rule, not a durable
GPR/publication-class equivalence, and optimizer absence alone remains
insufficient evidence outside this qualified panel.

Compute dispatch builtins do not each require a distinct provenance route.
Across direct store, homogeneous IADD, dependent address, and branch
consumers, local position, linear local index, SIMD lane, SIMD-group index, and
threads-per-threadgroup have byte-identical complete programs after replacing
one `get_sr` selector byte.  Cross-native selector recodes reproduce exact
alternate builtin oracles.  They therefore form one
`compute_system_scalar16_u32` machine class whose semantic identity is selector
metadata.  This is a machine-provenance merge, not a claim that the values are
interchangeable.

The remaining dispatch builtins expose genuinely different construction paths
in this panel.  Group position and grid index use direct 32-bit system-value
forms; threadgroups-per-grid is synthesized through a load and integer ALU;
SIMD-groups-per-threadgroup is derived from three system registers; and
threads-per-SIMD-group is emitted as the immediate architectural value 32.
The grid-index signature remains lifetime-confounded because the harness also
uses it to address the output.  These classes stay separate until a controlled
consumer/lifetime panel establishes a merge.

Dispatch geometry does not specialize these programs.  The same native binary
for each of nine public system values executes exactly under 64×16, 64×32, and
128×64 dispatches and produces distinct geometry-dependent full-buffer
oracles.  Package snapshots and coordinated one-field ablations resolve the
`threadgroups_per_grid.x` dependency: selector 168 is the local X size, while
resource-table entry zero points to the caller-owned `dispatchThreads` global
thread-count tuple at metadata offset `0xa8`.  The native program computes
`ceil(global_threads.x / local_size.x)`.  CDM grid dimensions independently
control how many invocations execute, and CDM local dimensions supply the
threadgroup system values.  Mesa must therefore author the global-count tuple,
publish its pointer through the launch resource/preload map, and encode total
and local dimensions in the CDM record.  The adjacent entry-one all-ones tuple
has not yet been assigned a semantic name.  `simdgroups_per_threadgroup` is
derived from the three local-dimension selectors 152/153/154, while
`threads_per_simdgroup` is the architectural immediate 32.  These construction
paths remain separate even when their final values enter the same broad
integer consumer class.

The tuple rule is independently checked by one asymmetric 3D package.  CDM
grid X/Y/Z is the physical invocation domain, CDM local X/Y/Z feeds selectors
168/169/170, and caller metadata X/Y/Z supplies both `threads_per_grid` and the
three ceiling-division numerators.  Native Metal emits three corresponding
metadata loads.  Five component-wise mutations plus a control execute exactly,
so this is a real tuple extension rather than an inference from the 1D form.

Direct and indirect dispatch normalize into this same shader construction.
Direct `dispatchThreads` publishes the requested global-thread tuple as entry
zero and an all-ones scale as entry one.  Indirect `dispatchThreadgroups`
publishes the raw caller record as entry zero and the API local-size tuple as
entry one.  The common semantic grid is `entry0 * entry1`; group count is its
component-wise ceiling division by CDM local size.  Four exact indirect runs
separately mutate the raw record, scale tuple, and CDM divisor.  The indirect
CDM record has a demonstrated generation-specific layout: mode word
`0x08880000`, split raw-record address at `+0x10`, local tuple at `+0x18`, and
a 0x28-byte record followed by the control-stream sentinel at `+0x28`.

Scalar texture, threadgroup, atomic-return, and subgroup-return producers also
remain distinct from `buffer_load_u32` and from one another.  Their exact
242-case panel is stable in both orders.  More importantly, an exhaustive
compute-ISELECT route mutation produces three different accepted-route sets:
`{6}` for buffer loads, `{1,7}` for texture and threadgroup results, and
`{0,1,2,3,4,5,6,7}` for atomic and subgroup results.  The route-insensitive
programs have separate selected-register sensitivity-positive controls, so
their result is genuinely observed.  Sharing one route set is still not class
identity: texture uses a distinct native U2F source form from threadgroup, and
atomic versus subgroup results have different producer and fragment-consumer
signatures.  A route set is one row of the compatibility signature, not the
whole provenance class.

Invocation-invariant fragment device loads form a separate constant-program /
uniform-preload class rather than another `buffer_load_*` spelling.  Across 21
matched integer and float conditions, native Metal consistently enlarges the
constant program beyond the ordinary 64-byte baseline and replaces or
substantially reduces the per-fragment main path.  Eighteen conditions expose
decoded `uniform_mov` instructions; the remaining three texture-coordinate
conditions still retain the distinct constant-program placement.  The semantic
source inventory continues to name the MSL construction, while the
architectural groups retain the source-class names
`fragment_uniform_device_u32` and `fragment_uniform_device_f32`.

`front_facing_u32` remains separate from ordinary integer ALU and materialized
predicate producers.  Across 11 matched fragment consumer/lifetime conditions
per pair, no pair has an identical complete active-stage fingerprint.  A
separate winding panel executes both boolean values: sum-of-two-materialized-
booleans and direct-select source forms compile to the same fragment program,
and that program is byte-identical across front and reversed winding.  Only the
vertex program changes, while every output pixel changes from result 2 to 0.
This retains the distinct stage-system producer and classifies the source IADD
relationship as a stable native normalization rather than a direct arithmetic
edge.

Fragment flat, linear, perspective, inverse-W, position, uniform-device, and
texture producers remain split.  Their common float-add/store panels expose
distinct iterator, uniform, texture, SFU, or ordinary ALU paths.  Semantic
differences such as interpolation mode are independently observable, so no
class collapse is justified by the current census.
