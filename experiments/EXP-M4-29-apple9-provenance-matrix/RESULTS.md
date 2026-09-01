# EXP-M4-29 results

## Evidence status

`HOMOGENEOUS-COVERAGE-QUALIFIED / MATRIX-UNRESOLVED`: eleven homogeneous
compute-select cells are promoted to `direct_native`; 43 compute-immediate
cells and one fragment cell are `native_normalized`.  The remaining 4,390
applicable cells are unresolved.  Schema v4's reduced homogeneous-tuple corpus
is qualified on T8132/macOS 26.6.2 build 25G83, but most direct versus
normalized routing still requires reviewed encodings and coordinated
ablations.

## Schema-v4 qualification

- The old schema-v2 generated seed contained 5,577 cells and 11,008
  fresh-process native cases.  The later pairwise schema-v3 seed grew to
  98,682 cells and 181,480 cases and is superseded as an execution plan: that
  corpus was too large and mixed class discovery with heterogeneous-tuple
  closure.
- Schema v4 contains 4,668 cells and 8,890 fresh-process cases over 38
  provisional producers and 56 consumers: 4,445 cells are stage-applicable
  before evidence promotion and 223 are explicitly stage-inapplicable.  This
  is a 20.4x case-count reduction from schema v3.
- `make_slices.py` greedily selected 157 single-use cells, with both A/B
  formulations, which cover all 242 emitted stage/consumer and stage/producer
  targets.  Both the 314-case forward arm and the 314-case reverse arm pass
  exact full-output comparison with no refusal, fault, hang, or order
  dependence under current corpus hash
  `2f49035c33874a70b3e2869716a8c3f666d909ecd27a343b6e271e3e47b3b36a`.
  All 157 A/B `_agc.main` pairs are byte-identical.
- The paired census extracts every `_agc.*` symbol from both pipeline stages:
  1,044 symbols, 21,620 decoded instructions, and no extraction error.  This
  includes constant programs rather than assuming all dataflow resides in
  `_agc.main`.
- A separate 35-case exact gate covers the higher-risk perspective/inverse-W,
  raw system-index, attachment input/output, texture-LOD, image-atomic, and
  vec4 device-load paths in both orders.  It also passes 35/35 with exact
  primary, stage-buffer, auxiliary-image, and depth oracles where applicable.
- A 364-case class-equivalence panel executes every provisional producer in
  every applicable stage through one common ALU and one common store form for
  its type.  It passes exactly in both orders; all 182 A/B cell pairs have
  identical `_agc.main` bytes.  The resulting 91 producer/stage signatures
  are retained in `CLASS_SIGNATURES.json`.
- Across all five scalar types and all three stages, `constant_*` and
  `device_*` have the same ALU/store mnemonic sequence and byte-identical
  `device_load` and terminal `device_store` records.  Differences are confined
  to address setup and register selection in this panel.  This is a strong
  merge candidate, not yet a merge: select, address, texture/atomic, conversion,
  shift/multiply, and fanout consumers are separately gated before promotion.
- That distinguishing panel contains 400 cases / 200 cells and passes exact
  complete-output comparison in both orders.  All 400 active-stage binaries
  are order-stable and all 200 A/B source-formulation pairs are byte-identical.
  Of 100 matched constant/device conditions, 84 have identical active-symbol
  mnemonic sequences.  Sixteen select+fanout conditions schedule address
  setup differently while retaining equal select, load, and store records.
  Six dependent-index conditions retain equal mnemonic sequences but use
  different register/address fields in the second load and terminal store.
  These were the bounded targets for coordinated route/release ablation; they
  were not interpreted by inspection.
- The paired compute `fselect` ablation gives constant- and device-space loads
  the same route-sensitive behavior in two repetitions: native state 11/route
  6 exact; route 1 alone deterministically changed output; selected load state
  00 under route 6 exact; and state 00/route 1 exact.  Pipeline archive input
  was confirmed for all 16 executions.  This promotes five type-specific
  `buffer_load_*` architectural provenance groups.  The ten source spellings
  remain independently generated and executed construction variants.
- A separate 204-case scalar/uint2/uint4 panel passes exactly in both orders.
  All 204 active-stage binaries are order-stable, all 102 A/B pairs are
  identical, all 68 scalar-to-vector comparisons preserve the coupled
  producer-state sequence, and all terminal stores match.  The 24-execution
  ISELECT ablation gives scalar, uint2, and uint4 the same route-sensitive
  signature with no unexpected outcome.  These source forms now share
  `buffer_load_u32`; width format and component offset remain construction
  metadata.
- A bounded 176-case GPR-candidate panel covers ordinary integer ALU results,
  zero/one predicate results, and raw compute/vertex system indices through
  integer select, dependent device index, unsigned-to-float conversion, and
  branch predicates.  It passes 176/176 exactly in both fresh-process orders;
  all 176 active-stage binaries are order-stable and all 88 A/B pairs are
  byte-identical.  This panel does **not** justify a merge.  Of 55 matched
  ordinary/candidate conditions, 21 have distinct expected-family bytes, 16
  lack the expected family only in the candidate, and 18 lack it in both.
  Predicate select forms differ from unconstrained integer ALU forms, while
  homogeneous raw-system select often leaves no separately identified select
  family.  Absence is recorded as an observation, not called a native bridge,
  refusal, or direct edge.  All three provisional architectural classes remain
  split; the focused raw-index witness below now closes the system-index side,
  while the predicate/ALU range-controlled comparison remains pending.
- A repeated terminal-ISELECT route census now distinguishes ALU results from
  materialized predicates behaviorally.  For the fanout-live1 ALU case, native
  route 2 is exact in 86/86 executions and route 7 in 74/74.  Each of routes
  0, 1, 3, 4, 5, and 6 produced at least one intermittent wrong-output run;
  across those routes there are 11 corrupt executions, usually confined to
  the second 32-lane SIMD group but once affecting the first.  The predicate
  case is exact for all routes across 26 native-route and 14 per-nonnative-route
  observations.  Independent selected-register mutations change full output
  for both.  The native forms are direct, but the accepted route signature is
  different, reinforcing the retained class split.
- The bounded immediate panel contains 172 cases / 86 cells and passes exactly
  in both orders.  Every active-stage binary is order-stable and all 86
  hex-versus-decimal A/B source pairs are byte-identical.  Across 43 matched
  immediate-versus-same-type-ALU conditions, none has an identical complete
  native program.  Metal eliminates the original consumer in 35 immediate
  conditions by compile-time evaluation; their exact resulting active-symbol
  programs are recorded per cell.  The eight retained side-effecting or
  texture consumers (`atomic_data`, integer texture coordinates, and float
  sample coordinates) all contain explicit literal materialization.  The two
  atomic lifetimes share one 16-byte pre-consumer signature, the three integer
  texture lifetimes one 14-byte signature, and the three float texture
  lifetimes one 20-byte signature.
- Fourteen repeated archive-input executions qualify those retained bridges.
  Unmodified controls are exact.  Changing the load-bearing integer prefix
  changes atomic and integer-texture output deterministically.  For float
  coordinates, changing the compact prefix is an exact negative control, while
  replacing only the two literal payload words with those from an independently
  compiled alternate Metal workload changes output to that workload's exact
  oracle.  `IMMEDIATE_MATERIALIZATION_RESULTS.json` validates the complete
  chain.  The 43 immediate source cells are therefore `native_normalized`;
  literals remain distinct from runtime ALU results as machine provenance.
- A compact compute-system-value panel covers ten public builtins through
  direct store, homogeneous IADD, dependent constant-buffer address, and
  branch-predicate consumers.  Its corrected 80 cases / 40 cells pass exactly
  in both source formulations and both fresh-process orders.  The initial arm
  mixed scalar and `uint3` position/size declarations; Metal rejected those
  four source families with the public same-dimensionality diagnostic.  That
  arm is retained as invalid harness input, not a provenance refusal.
- Local position, linear local index, SIMD lane, SIMD-group index, and
  threads-per-threadgroup form one `compute_system_scalar16_u32` machine
  provenance group.  For every consumer, their complete programs are identical
  except for one `get_sr` selector byte (164, 167, 130, 133, and 152
  respectively).  Eight selector-only recodes from local position to each of
  two independently compiled native targets reproduce the target's exact
  full-buffer oracle in two repetitions; four unmodified controls are exact in
  two repetitions.  Semantic builtin identity remains selector metadata.
- Five other builtins remain separate pending more consumers: grid index is a
  direct 32-bit system value but is implicitly reused as the harness output
  address; group position uses another direct 32-bit form; threadgroups-per-grid
  is synthesized through a load/ALU chain; SIMD-groups-per-threadgroup is
  derived from three system registers; and threads-per-SIMD-group is
  materialized as the immediate architectural value 32.  These distinctions
  are directly relevant to Mesa packaging: not every public dispatch builtin
  is delivered through the same raw system-register form.
- Dispatch geometry is now an explicit runner input rather than a hidden
  constant.  A 54-case / 27-cell follow-up executes nine system values under
  64×16, 64×32, and 128×64 1D configurations.  Every case is exact in both
  source formulations and both orders.  For each system value, the complete
  shader binary is byte-identical across all three configurations while the
  full-buffer oracle changes in at least one configuration.
- Three caller-owned package snapshots and five single-field ablations now
  resolve the `threadgroups_per_grid.x` construction.  Bare `get_sr(168)` is
  `threads_per_threadgroup.x`, not the grid count.  Resource-table entry zero
  points to the `dispatchThreads` global-thread-count tuple at dispatch
  metadata offset `0xa8`; Metal loads that numerator, adds local-size minus
  one, and performs integer reciprocal/divide lowering.  Redirecting the
  pointer from 64 to an adjacent value of one reports one group, proving
  ceiling rather than floor division.  Independently changing metadata 64 to
  96 changes 64 invocations from four to six groups, changing the CDM grid to
  96 changes only the invocation count, and changing CDM local X from 16 to 32
  changes the reported group count from four to two.  Every arm compared the
  complete 4-KiB buffer exactly.  The shader/archive and launch wrapper were
  invariant across 64x16, 64x32, and 128x64 dispatches.  Entry one points to an
  adjacent all-ones tuple; its semantic role remains unresolved.
- The other geometry rules remain unchanged: `simdgroups_per_threadgroup` is
  derived from dimension selectors 152/153/154 and changes from one to two for
  a 64-thread group, while `threads_per_simdgroup` is emitted as immediate 32.
  The first geometry arm's SIMD-lane oracle incorrectly assumed lane numbering
  continued across 16-thread groups; hardware showed the lane restarts per
  group, and the corrected arm is retained separately.
- One asymmetric 12x10x6 dispatch with a 4x5x3 local size extends that contract
  to all dimensions without a broad case expansion.  Its exact native shader
  reads local selectors 168/169/170 and issues three metadata loads with the
  corresponding decoded spaces 16/32/64.  Component-wise mutations of metadata
  X/Y/Z and CDM local Y/Z all produce exact complete-buffer oracles, including
  ceiling cases 13/4, 11/5, and 7/3.  The CDM grid remains the physical
  12x10x6 invocation domain while the metadata tuple independently supplies
  both `threads_per_grid` and the numerators for `threadgroups_per_grid`.
  Two initially rejected X/Y oracles are retained: they forgot that changing
  `threads_per_grid` also changes the shader's row/plane output stride, and the
  observed first holes occurred at exactly those corrected strides.
- One asymmetric indirect 5x3x2-threadgroup dispatch with a 4x4x1 local size
  uses the byte-identical shader archive and launch wrapper as the direct 3D
  case.  Its resource entry zero and indirect CDM pointer both identify the raw
  caller-owned threadgroup record; resource entry one points to a local-size
  scale tuple.  Exact single-field mutations establish the normalized rule:
  `threads_per_grid = raw_groups * scale`, followed by component-wise
  `threadgroups_per_grid = ceil(threads_per_grid / CDM_local)`.  Mutating raw X
  from 5 to 6 expands physical execution and reports six; changing only scale X
  from 4 to 8 preserves physical execution but changes the public grid stride
  and reports ten; changing only CDM local X from 4 to 2 contracts physical
  execution and also reports ten.  All four complete buffers match independent
  CPU oracles.  Direct `dispatchThreads` is the same construction with a global
  thread tuple and an all-ones scale; indirect `dispatchThreadgroups` uses raw
  groups and the API local-size scale.
- A hash-closed six-case supplement removes the canonical dependent-index
  mask while keeping all 64 dynamic indices in bounds.  It passes 6/6 exactly
  in both compilation orders; all three A/B cells are byte-identical.  Native
  Metal emits `get_sr` followed immediately by a constant-space `device_load`
  selecting index register 1 (`space=16`), with no intervening ALU.  An
  ALU-derived in-bounds index instead uses `index_reg=128, space=0`.  Replacing
  only the direct load's selected address register changes the complete output
  deterministically in two archive-input repetitions, while both unmodified
  controls remain exact.  `RAW_SYSTEM_INDEX_RESULTS.json` therefore closes the
  raw direct-consumer witness and retains `system_index_u32` as a distinct
  producer signature.
- A 32-case range-controlled compute supplement compares shift/mask ALU-bit
  spellings with boolean materialization while forcing both to produce the same
  runtime 0/1 values.  It passes 32/32 exactly in both orders.  Seven of eight
  select/address/conversion/branch and single-use/fanout conditions compile all
  four producer/formulation arms to the same complete native program.  In the
  eighth (branch plus fanout), one predicate spelling takes a distinct optimizer
  path, but the alternate predicate spelling again matches both ALU spellings.
  The shared fanout-ISELECT form is exact at all eight route values for 14
  repetitions each, while changing its selected register changes output in all
  14 repetitions.  This matches the materialized-predicate route signature,
  not the full-width ALU signature.  The result does not merge broad
  `alu_u32` and `predicate_u32`; it discovers a range-constrained/bit-extract
  machine class that both source families normalize into.  It will enter the
  next schema inventory without invalidating the current v4 capture hashes.
- A separate 242-case return-producer panel compares scalar buffer loads,
  texture reads, post-barrier threadgroup loads, atomic returns, and subgroup
  returns through the same select, dependent-index, conversion, and branch
  consumers.  It is exact 242/242 in both orders; all 242 active-stage binaries
  are order-stable and all 121 A/B pairs are byte-identical.  The 88 matched
  buffer/candidate conditions include 22 byte-identical terminal consumers,
  36 same-family/different-byte consumers, six different consumer families,
  and 24 conditions in which an expected family is absent on one or both
  sides.  Equal terminal bytes alone are not used to merge producer classes.
- The paired 80-execution compute-ISELECT route census gives three repeatable
  acceptance signatures with archive input confirmed throughout: buffer-load
  values are exact only at route 6; texture and threadgroup values are exact
  at routes 1 and 7; atomic and subgroup values are exact at all eight route
  values.  Independent selected-register mutations for the latter two change
  full output in both repetitions while their unmodified controls remain
  exact, so route insensitivity is not a dead-output artifact.  These are
  bounded consumer signatures, not complete class merges: native U2F already
  distinguishes texture from threadgroup, while producer forms and fragment
  signatures distinguish atomic from subgroup.
- A 126-case fragment-uniform panel is exact in both orders, with all 126
  active-stage binaries order-stable and all 63 A/B pairs byte-identical.  It
  compares ordinary constant/device indexed loads with invocation-invariant
  fixed-index device loads through integer and float select, conversion,
  dependent address/texture-coordinate, and branch consumers.  Every one of
  the 21 matched uniform conditions is architecturally distinct from the
  ordinary device case: its constant program grows beyond the 64-byte baseline
  and its main program changes substantially; 18 conditions explicitly use
  `uniform_mov`, while the three texture-coordinate conditions retain the
  distinct larger constant program without that decoded mnemonic.  The
  invocation-invariant sources are therefore retained as
  `fragment_uniform_device_u32/f32`, not folded into `buffer_load_u32/f32`.
- A 66-case fragment-boolean panel is exact in both orders; all 66 active-stage
  binaries are order-stable and all 33 A/B pairs are byte-identical.  Pairwise
  comparison of integer ALU, materialized-predicate, and `[[front_facing]]`
  producers covers 11 matched select/index/conversion/branch conditions per
  pair.  None of the three pairs has an identical complete active-stage
  fingerprint; 22 comparisons have distinct consumer-family bytes and only
  one has equal consumer-family bytes.  `front_facing_u32` remains a separate
  stage-system producer.  A four-case winding supplement now crosses genuinely
  different sum-versus-direct-select source formulations with front and back
  full-screen geometry.  All four cases pass exactly in both orders, and every
  fragment-stage symbol is byte-identical across formulation and winding while
  only the vertex program changes.  The complete target changes from IADD
  result 2 to result 0, closing both semantic values and proving the native
  source normalization.
- `classifications.json` promotes eleven narrowly evidenced homogeneous compute
  cells to `direct_native`: scalar/uint2/uint4 buffer results feeding
  ISELECT, texture/threadgroup/atomic/subgroup results feeding ISELECT, and
  constant/device float loads feeding FSELECT, plus fanout-live1 ALU and
  materialized-predicate results feeding ISELECT.  Each promotion has exact A/B
  execution in both compilation orders, an all-symbol producer-to-consumer
  census with no inserted bridge, and a coordinated route/state or independent
  sensitivity ablation.  The fragment front-facing IADD cell is separately
  promoted to `native_normalized`: two independent source forms compile to the
  same `get_sr`/select program, and winding alone supplies an exact semantic
  sensitivity-positive arm.  No normalization is inferred from missing
  instructions alone.
- The native runner now validates every selected source and oracle against
  `generated/manifest.json` before creating a capture.  This was added after
  a deliberately rejected mixed-version staging arm exposed a stale guest
  oracle; that aborted arm is not evidence.
- Native `sin` is observed through an exact post-consumer integer
  quantization.  Raw Apple and host-libm sine results differ by one ULP for
  some inputs, which is a numerical approximation issue rather than a
  provenance failure.  The quantized compute and fragment probes pass in both
  orders.
- Fragment subgroup reduction uses an invocation-invariant ALU producer so
  the oracle does not assume the hidden pixel-to-SIMD lane permutation.  The
  compute and fragment reduction cases now pass exactly in both orders.
- Minimal half4 and uint4 explicit-layout fragment imageblocks are both
  rejected by the public 25G83 compiler with the same undefined-template
  diagnostic.  They are retained under `captures/imageblock-type-control` as
  refusal evidence and removed from the emitted-class matrix.  Programmable
  blend attachment input remains the valid fragment attachment producer.
- Thirty-two role/formulation cases across compute, vertex, and fragment pass
  complete output comparison, including each live-after role of a four-source
  select.
- Thirty-six distant, control-flow, and pressure cases pass across all three
  stages.  All 18 A/B pairs have identical `_agc.main` hashes.
- Real vertex/fragment device stores are compared through a separate 4-KiB
  stage buffer.  Float color-output cases use RGBA32Float rather than an
  integer proxy target.
- Archive-input qualification reproduced an unmodified IADD exactly twice and
  a single source-B-register mutation as changed output twice.  Every run
  confirmed `FailOnBinaryArchiveMiss` archive input.
- Periodic exact baseline checks stayed healthy and no case watchdog fired.

These are harness and relationship witnesses, not yet `direct_native`
classifications.  Direct versus normalized still depends on the all-symbol
instruction census and coordinated rule-specific mutations.

## Required final artifacts

- Two fresh-process native capture orders with identical sources and exact
  outputs.
- A complete homogeneous producer/consumer matrix with no applicable
  `unresolved` cells before the separately gated heterogeneous-tuple phase.
- Distinguishing hardware witnesses for every retained class split.
- Stable native bridges for every `native_normalized` cell.
- Public Metal diagnostics and minimal sources for every `native_refused`
  cell.
- Coordinated ablations for every distinct publication/route/lifetime rule.

## Prior-evidence reconciliation

Older experiments are treated as probe seeds.  They are not automatically
promoted because several historical failures changed a load destination,
publication token, release field, and consumer route independently.  This
experiment replays the complete native tuple before assigning causality.
The detailed machine-readable disposition is in `SUPERSESSION_LEDGER.json`.
