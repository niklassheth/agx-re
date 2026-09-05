# T8132 render size and clipping fixes — 2026-09-05

Artifact paths in this note are relative to
`/home/nsheth/Projects/asahi/tmp/apple9-render-bugs/` unless stated otherwise.

## Resolution: separate tile-map and heap-control storage

The 1024-square failure reproduces with the ordinary three-vertex triangle,
without the island, complex fragment math, or a depth attachment. Both 1024×512
and 512×1024 complete. A diagnostic 1024-square run records a context-2 GPU fault
at 0x1000390000 after TA retirement and before fragment completion. Raw event
and KTrace *data records*, not firmware instructions, are saved in
square-diag/diagnostics.json.

The kernel allocation placed heap/layer metadata at tilemap+0x1000. The tile map
uses sixteen macrotiles of size1 dwords each; at 1024×1024 its extent is 0x1400,
which overlaps that metadata. The smaller rectangular maps fit before it. At
768-square, the padded macrotiling has unused regions, so the corruption is not
triggered in the demonstrated workload.

`g16g_render.py` now gives heap/layer metadata a separate 16-KiB page at the end
of the private kernel allocation. Existing scratch offsets and fixed aliases
are unchanged. Kernel-range sizing/mapping includes the new page. This fixes
the overlap rather than adding a mapping for the resulting bogus fault address.
The 1024-square basic triangle then completes twice with identical attachments.
This is not a claim about the maximum supported render size.

## Clipping: native coefficient-aware projective multiplication

The authored EXP-M4-59 nine.metal fragment program contains a distinct scalar
multiply form: operation selector 7, eight-byte encoding, GPR operands plus a
coefficient index in byte 5. Its coefficient operand matches the corresponding
ITER coefficient. Only the `_agc.main` region of that authored shader was
examined; no helper/launcher or proprietary Apple algorithm was disassembled.
The isolated source-correlated instruction at main+0x82 supplies the packer
oracle; source/archive and extraction provenance remain in EXP-M4-59 and the
existing own-container parser.

Mesa now models this as `FMUL_PROJECT` / `FLOAT2_PROJECT`, reachable from normal
smooth input lowering. It uses allocator-selected FP32 GPRs in the measured
six-bit operand range. The coefficient index is explicit IR data and is checked
against the supported coefficient range. It is not an ordinary multiplication:
it correctly handles the native primitive-constant coefficient representation.

The VS exports ordinary values; shade-7 CF bindings and the fragment projective
multiply handle projection after homogeneous clipping. The old VS reciprocal-W
predivision is removed. This simultaneously fixes constant components and the
large clipped water mesh, so the scene's CPU frustum-fitting workaround is gone.

Initial testing also copied two native W-path control bits (ITER byte6=4 and
FRCP byte9=1). Removing both produced the same exact unequal-W oracle result.
Neither is introduced into the final compiler; existing ordinary ITER/FRCP forms
are retained. The necessary change is the coefficient-aware multiply together
with unprojected VS outputs and perspective CF bindings.

## Validation

* 191 compiler tests pass, including a new projective-multiply packer/operand
  constraint test and the existing semantic varying-layout checks.
* 169 G16 shim tests pass, including tilemap/metadata non-overlap tests for the
  square and rectangular cases. The first pytest invocation used the workspace
  root and had three relative-path failures; rerunning from the m1n1 root passed.
* `project-perspective` and `project-plain` pass both unequal-W frames exactly,
  including primitive-constant components. The latter excludes the extra bits.
* `project-water` passes two 768-square frames with the enlarged, hardware-clipped
  water mesh and no scene workaround.
* `square-fixed` passes two 1024-square basic triangle renders.
* `sunset1024` completes 16 frames / 8 viewpoints with both fixes and unclamped
  water. All final color/depth checks pass, max color error one byte, max depth
  error 4.202966e-6, four slope-bounded subpixel depth pixels, no order-dependent
  depth changes. No partial render or TVB growth occurs.
* The varying regression suite and individual reports are in `regressions.log`
  and `reg-*`; final aggregate counts are in SUMMARY.json.

The independent sunset oracle now uses double-precision clip intersections of
FP32 vertex shader outputs. Repeated FP32 intersections of the large triangles
crossing W=0 introduced a false depth-plane offset in the reference. The original
comparison is retained in `sunset1024/validation-fp32-clip.json`; using higher
precision fixes the reference without widening any tolerances. The original
near-edge and local depth-slope allowances remain explicit and reported.

No commits or pushes were made. The diagnostic-only raw-record logging was
removed; g16g_device.py matches its saved pre-task contents.

Final gate: all nine varying cases (18 frames), 16 sunset frames, and two
basic-triangle frames pass: **36 final hardware renders**. The near/far-plane
case covers 28,160 pixels and has at most one byte of color error. All 191
compiler tests and 169 shim tests pass; both repositories pass diff checks.
