# EXP-M4-20 results — Apple9 render instructions and Dynamic Caching

## Setup

The M4 mini booted macOS through a freshly chainloaded `m1n1.bin` built with
`EXTRA_CFLAGS=-DNO_DISPLAY`.  The guest ran under `run_guest.py`.  All tested
Metal shaders are in `render_lifetime.metal`; `capture_guest.sh` retained the
caller-owned archives, and `splice_render.py` changed one instruction field at
a time before a 16x16 off-screen draw.

Every negative result below has an adjacent positive control that changes an
actual operand or render-target selector and visibly changes the output.  This
rules out a broken splice path or an unobserved shader body.

## Required instruction surface

The first useful Apple9 shaded triangle needs the following machine families:

- Vertex: `get_sr` for vertex ID, integer compare/select, scalar float ALU,
  constants, position output, and user-varying stores.
- Fragment: linear/smooth/flat iterators, reciprocal and multiply for
  perspective interpolation, scalar ALU/select, color conversion/packing,
  tile-buffer setup, color store, completion fence, and stop.

`captures/analysis.txt` contains the raw bytes and decoded fields for constant,
linear, perspective-smooth, flat, arithmetic-DAG, select, fanout, and
32-varying pressure shaders.

## Stage-specific `0x54/0x55/0x56` field

The byte seen as `0x54` in many stage-specific instructions is **not** a
mandatory general source-release bit under the tested conditions.

The following mutations all rendered byte-exact baseline images:

- Vertex user-varying store mode `0x54 -> 0x55` and `0x54 -> 0x56`, at the
  first, middle, and last store.
- Fragment iterator mode `0x54 -> 0x55` and `0x54 -> 0x56`, including the
  perspective-W iterator.
- Perspective reciprocal mode `0x54 -> 0x55` and `0x54 -> 0x56`.
- Fragment color-pack class `0x54 -> 0x56`, separately and together for both
  pack instructions.
- Fragment tile setup and color-store mode `0x54 -> 0x56`.

The pressure shader exported 32 user-varying components in addition to
position and consumed all 32 components in the fragment stage.  Changing all
32 user-varying stores to `0x55` or `0x56`, or all 32 fragment iterators to
`0x55` or `0x56`, still produced the exact baseline image.  This closes the
simple explanation that the low-pressure cases only worked because no value
was evicted.

The conservative compiler model is therefore: retain this field as a
stage-specific mode/advisory field until a counterexample identifies a
semantic effect.  Do not map it to the ordinary Apple9 source-lifetime bits.

## Ordinary ALU lifetime state in render

The ordinary scalar ALU forms do follow the Dynamic-Caching model established
by the compute experiments.

### Per-source release

In `linear-fanout`, a fragment `falu2` at `+0x20` has one source consumed for
the last time and one source reused later:

- Clearing the native last-use bit on the dead source was exact.
- Setting the release bit on the retained source corrupted its later reuse.
- Clearing destination state was exact in this instance.

In `linear-dag`, the first min/max at `+0x38` reuses both sources later.
Setting source-A release, source-B release, or both produced three distinct
wrong images.  The second min/max at `+0x3e` has two dead sources; clearing
either or both native release bits was exact.

The eight-byte select at fragment `+0x28` behaves the same way.  Bits 19 and
20 are the compare-source lifetime bits: setting either destroyed the
corresponding later red or green reuse, and setting both destroyed both.

### Consumer route

Consumer route is provenance/form dependent, not a universal opcode mode:

- The `linear-fanout` ALU consumer requires route 4.  Routes 0--3 produced one
  wrong result class and routes 5--7 another.
- All routes 0--7 were accepted by the first `linear-dag` min/max when its
  operands came from iterator/ALU producers.
- All routes 0--7 were accepted by the eight-byte select with iterator-fed
  compare operands.
- All routes 0--7 were accepted by the perspective multiply in
  `smooth-fanout`.

This confirms the compiler must derive the consumer route from producer
provenance and encoding form.  It must not assign one route per operation.

## Positive controls

The following one-field changes produced visibly different hashes/pixels:

- Vertex varying-store source register `r4 -> r1`.
- Fragment iterator varying slot `0 -> 2`.
- Fragment color-pack value source.
- Fragment color-store target `RT0 -> RT1`, which left RT0 zero.

## First compiler consequence

The evidence supports a fail-closed first fragment compiler for one smooth
`vec3` varying to RT0.  It may use the measured iterator/reciprocal/float-ALU
sequence, explicit per-source release bits, proven producer routes, two color
pack operations, tile setup, color store, fence, and stop.  The next compiler
increments should generalize in this order:

1. Fragment arithmetic DAGs using the existing Apple9 virtual SSA/liveness
   model and the render-proven release/route rules.
2. Linear/noperspective and flat interpolation.
3. Vertex output construction and varying stores.
4. Constant color and multiple varying shapes.
5. Depth/discard/blend/MSAA only after new focused traces.

The results do not yet assign semantics to every render instruction bit, nor
do they prove `0x54/0x55/0x56` is irrelevant in all workloads.  They establish
that it is not required as a general Dynamic-Caching lifetime mechanism for
the tested low- and high-pressure render programs.

## Mesa compiler milestone

The first bounded Mesa render compiler now consumes the actual lowered NIR
for both stages:

- Vertex: vertex ID, position/color UBO addressing, clip-Z transform,
  fixed-point size, and UVS slots 0--7.
- Fragment: smooth `VAR0.xyz`, explicit opaque-color envelope, RT0 packing,
  tile setup/store, fence, and stop.

Both selectors reject unknown NIR shapes.  They emit the validated program as
individual instructions and own the resulting stage allocations; the old
static vertex and fragment arrays have been removed from the Gallium render
path.  Unit tests compare both emitted stages byte-for-byte against the
hardware-proven programs and exercise rejection paths.

A fresh T8132 run with both stages compiler-generated completed two real
TA+3D submissions through the DRM shim.  The first attachment changed all
1,048,576 bytes; the second changed 247,860 bytes with SHA-256
`acd4ed345d584d2c04ed99a5f0e6e84e292f9886dbda0b8a6c56a0534f2ad354`.
The test ended with `T8132_GLES_TRIANGLE_OK` in:

`logs/t8132_apple9_render_compiler_both_20260826_180352.log`
