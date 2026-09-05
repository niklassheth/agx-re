# EXP-M4-57: graphics UBO bindings and per-draw state

T8132 M4, macOS 26.6.2 25G83 captures; standalone Mesa/m1n1 validation,
2026-09-04.

## Provenance and scope

`probe.metal`, `probe.m`, and `probe-two.m` are our source. The public Metal
API compiles the shaders and binds explicit vertex and fragment data. The
capture records caller GPU buffers and state at the held work doorbell.
Opaque launch/helper code is retained without disassembly or decompilation.
Neither Metal-generated API shader main is included in the Mesa preload blob.
Source-correlated buffer loads in the authored mains establish slot zero for
each stage; both constant programs have the existing 64-byte trivial form.

`extract_preloads.py` reproduces the 512-byte external preload/state artifact
from the pinned native capture. Its SHA-256 is
`3840a61cb6cbaf17aae247766001a90663f493e2fa1e72791ca14c6e9d1ecafe`.
The production compiler emits semantic UBO loads and API binding metadata.
Fixed capture offsets and opaque bytes remain in the compatibility packager
and external artifact, not in compiler instruction selection.

## Binding and selection observations

- The first captured VS data lives at `USC+0x200090`, pointed to by a qword
  table at `USC+0x2000c0`. FS data lives at `USC+0x2108f0`, pointed to by the
  table at `USC+0x348600`. These locations were found from our known input
  bytes and exact pointer values, without decoding executable instructions.
- The known compact pointer grammar names the VS table from the launch at
  `USC+0x220000`, and the FS table from the launch at `USC+0x230640`.
- In the two-draw capture, each additional launch occupies 0xc0 bytes. Opaque
  first/second launch comparisons differ only in the compact table reference:
  VS bytes +1/+4 and FS byte +1. Both draws share the shader calls.
- VDM word +0x0c changes from 0x8800 to 0x8803 although the output interface
  does not change. It selects the VS launch in 64-byte units; it is not an
  output count. The old `vertex_outputs` model has been corrected.
- The FS state record's word +0x14 changes from 0x8c19 to 0x8c1c, also naming
  the next 0xc0-byte launch in 64-byte units. Standalone relocation controls
  and the final distinct-draw oracle independently validate both selectors.

## Implementation and validation

The shared compiler uses graphics argument slot zero, separately from the
compute launcher ABI. Each stage exports its active API UBO binding mask.
Graphics vectors are scalarized into ordinary scheduled memory loads, including
constant matrix-column offsets. Multiple active UBOs in one stage fail closed.

Gallium retains the actual UBO BO/range at each draw. At synchronized submission,
it publishes separate aligned pointer records, opaque preloads, and FS state
records. Both fixed and package-relative USC views receive the same snapshots.
Shader code remains shared across draws and uniform values. The initial arena
holds 32 uniform-bearing draws per batch.

Early attempts stalled. They combined an incremental native 0x700 PPP record
with this encoder's full-state sequence and initially shared inadequately
separated pointer records. Subsequent positive controls separately established
that a relocated regular FS launcher works, a separate full-state 0x500 PPP
record works, and the aligned uniform preload works with a known Mesa FS body.
The final implementation uses the full-state 0x500 packet, separate 32-byte
pointer records, and the existing constant programs/root binding mode. The
failed variants do not independently establish every minimum alignment or
bit-level requirement. Temporary shader substitution and binding probes were
removed before the successful complete tests.

Hardware results:

- FS-only glUniform tint: 33,792 covered pixels, every color exact.
- Both stages: two three-vertex draws per frame, distinct mat4 transformations
  and vec4 tints, followed by a scalar time change in frame two. Every pixel
  matches the independent CPU oracle: 18,432 pixels per triangle, no coverage
  errors, maximum channel error zero.
- Explicit std140 UBOs at API bindings 4 and 7, using distinct per-draw ranges:
  the same two-frame oracle passes, byte-identical to ordinary glUniform.

Frame hashes for both API paths:

- `3fcc86f61e25ef83fc4416adefd77a2bb20ad35b685ac4a30fa1b6d208730726`
- `fde6907db327168856067d14be718e3bc261f71165f4c67dba3c3a0b32122ea7`

The reusable GLES scene, block variants, runner, and raw-attachment validator
are in `mesa-m1n1-shim/src/asahi/drm-shim/scenes/uniforms/`.

Final checks: all 187 compiler tests pass, including constant-offset vector
UBOs in both stages and rejection of multiple UBOs without a diagnostic
pointer. The existing 100-triangle scene still passes both hardware frames
with its original attachment hash
`b611f28ff66e5b1eac15b1b92380c4413df5cc98a7cf54f1f23d370cd1c2d86b`.
