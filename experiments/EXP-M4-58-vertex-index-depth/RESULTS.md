# EXP-M4-58 — vertex buffers, indexed draws and depth

Target: T8132 M4 Mac mini. Native captures use macOS 26.6.2 25G83. Mesa
validation runs standalone through the m1n1 DRM shim, 2026-09-04.

## Provenance

`probe.m` / `probe.metal` are authored sources using public Metal APIs. Each
stage explicitly reads four independently bound constant buffers. The probe
issues a u16 indexed triangle; its depth variant adds Depth32Float, clear 1,
LESS comparison and writes. Full caller-buffer captures were saved at a held
work doorbell and then executed. No proprietary binary was disassembled or
decompiled. Raw comparisons of opaque launch records and data/command pointers
were used; the compiler emits its own semantic API shader mains.

- `native.pkl.gz`: `c40db3241ebdf3bf9b4f9f25d7f868ac4cceb2c5e96434e94fe2cf70896afd31`
- `native-depth.pkl.gz`: `81d4d38767e295a5f19550a7e15657dfcbc184f8089dfe3b01f6595e188b939e`
- `render_buffers_launch.bin`:
  `2c2c906598a3993ef31999a6d9dfd004f598eb660dd0c106be095f339baad67c`

`extract_preloads.py` checks the native capture hash and extracts only two
opaque 0xc0-byte launch records (VS USC+0x220000, FS USC+0x230640). The API
mains reside separately in the archive. The compatibility packager patches
only the known compact pointer-table reference and archive selector (+0x36).
The previous one-buffer preload used +0x46 and a separate state reference;
those older offsets must not be applied to this record.

## Findings

1. The old single-pointer preload cannot simply be given a larger table. A
   two-attribute shader retired with only the clear image. A one-attribute
   position fetch produced the correct image (82,620 covered pixels, all
   colors within one level), isolating the additional argument slots. The
   four-buffer preload then passed the complete two-attribute triangle.
2. Authored bytes identify VS data at USC+0x200090/c0/f0/0x200120 and its
   four-qword table at +0x200160. FS data lives at +0x2108f0/920/950/980 with
   its table at +0x348600. Hardware validation later exercised all four VS
   slots with three vertex elements and a transform UBO.
3. Existing M4 CMD-4 packet measurements and the new capture agree: u16/u32
   indexed triangle opcodes 0x61f2/0x61f4, restart comparand, USC-relative
   index pointer, count, instances, signed baseVertex field, dword extent
   minus one, and tail word 1. The index pointer is not an ordinary low
   address. The existing m1n1 parser already modeled this address domain.
4. The depth-enabled capture changes PPP +0x34 from 0x40200 to 0x200 and both
   face words from 0x07200f00 to 0x01000f00. The previously documented compare
   bits [26:24] and write-disable bit 21 suffice for the tested depth states.
   No new m1n1 depth support was needed: its render UAPI path already carries
   depth addresses, clear values, strides, flags and stores.
5. Vertex elements must be selected by NIR's compacted `base`, not the GL
   semantic location. Sparse attributes at API locations 3/9/13 validate this.
6. The independent cube depth reference initially differed by up to 9.1e-6.
   Snapping projected XY to 1/256 pixel before forming interpolation planes
   reduces errors to floating-point rounding (under 2e-7 in the initial four
   angles). It also removes the initial 0–2 boundary coverage differences.
   Depth itself is never quantized in the reference. A later angle landed
   within one float ULP of a subpixel rounding threshold; evaluating the
   matrix product and viewport in FP32 (matching the emitted separate
   multiply/add operations), then rounding positive halfway screen positions
   upward, fixes that reference mismatch as well. At angle 12, ties-to-even
   differs by up to 1.28e-5 in depth; ties-up gives 9.73e-8. Neither depth
   tolerance nor shader code was changed to accommodate this.

## Mesa implementation

Vertex attributes lower to ordinary scalar UBO-style loads with a reserved
internal binding namespace. They use the common VIR, scheduling, allocator,
and memory encoder. Format and stride determine shader variants; addresses
and source offsets stay draw state. Missing float components default to zero,
except W defaults to one. UBO and vertex arguments share a four-pointer stage
budget. API UBO bindings and ordered hardware arguments remain separate.

Index resources use the low-VA/USC allocator, including user-index uploads.
Draw records carry counts, actual index offsets and extent. Each draw retains
its buffer resources. Depth and FS records are independently snapshotted in
the bounded 32-draw compatibility arena. Both color and depth paths use
Mesa-generated vertex and fragment mains.

## Validation

Artifacts are in `/home/nsheth/Projects/asahi/tmp/apple9-mesh-work/`:

- `quad/`: u16, four shared vertices, two triangles, separate padded VBOs,
  nonzero attribute/index offsets. 98,304 pixels; exact color/coverage;
  reversed order identical. Hash
  `91f16197884097e8f90cfc30ff6b3caa85825a64fe7abc55986bff14dc8e5fcf`.
- `quad32/`: u32 plus four VS arguments and sparse API locations. Exact color
  and coverage. Hash
  `7724b285fd42bf63ef0d08cff779b38e468aacb07faba8181d6780f1651dde22`.
- `depthstates/`: ten frames, 73,728 covered pixels, every color and depth
  checked. LESS/GREATER writes, disabled writes, disabled depth testing,
  ALWAYS/NEVER changes inside one batch. All pass.
- `rotation/`: 28 cube frames, eight shared vertices and 12 triangles,
  uniform-driven rotation, primitive-order pairs and full color/depth oracle.
  All pass: zero coverage/boundary differences, maximum color error one,
  maximum depth error 1.8679762414652856e-7. Color and depth hashes match
  within all 14 reversed-order pairs. `rotation.png` is a lossless animation
  of hardware pixels, with each frame compared back to its source PNG.
  See `validation.json` for per-frame hashes.
- `uniforms/` and `blocks/`: both original frame hashes retained exactly.
- `hundred/`: original 100-triangle hash retained exactly.
- `complete-tests.log`: all 188 compiler tests pass.

Initial scope and reproduction live in Mesa `scenes/mesh/README.md`. No commits
or pushes were made. Existing unrelated worktree changes were preserved.
