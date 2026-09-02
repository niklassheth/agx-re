# EXP-M4-39 results

Status: the eight-buffer superset carrier is integrated and passes the full
one-through-eight ordinary GLSL resource-count ladder on T8132.

No proprietary Apple executable is disassembled or decoded in this
experiment. The constant and external launch programs remain opaque. Package
pointers and resource records are manipulated only through the independently
established structural grammar.

## Native controls

The own-source Metal workload passed exact complete-output and guard checks on
macOS 26.6.2 build 25G83 for:

- `64x1x1`, local `16x1x1`;
- `9x7x1`, local `4x2x1`;
- `5x4x3`, local `2x2x1`; and
- nonzero offsets on all eight visible buffers.

Archive, launch, and Dynamic Caching state images were identical across those
geometry variants. Edge workgroups report their actual clamped
`threads_per_threadgroup` dimensions.

The normalized control is native work-doorbell ordinal 5926 in
`raw/native-8`. Its resource record contains:

| Qword | Meaning |
|---|---|
| 0 | pointer to the three-word grid tuple |
| 1 | pointer to the adjacent `{1,1,1}` tuple |
| 2 | pointer to an integer reciprocal/division helper table |
| 3-10 | eight visible buffer addresses |
| 11 | zero sentinel |

The first 8 KiB at qword 2 are byte-identical across the 1-D, 2-D, 3-D, and
offset captures. Contents after that table vary with the surrounding allocation
arena and are not part of the carrier.

## Reconstruction and ablations

The unmodified normalized package replayed with the exact native output oracle.
The following independent changes also passed exact hardware output:

- relocating qwords 0 and 1 into the per-dispatch resource record;
- relocating qword 2 while copying only its invariant 8-KiB table;
- replacing the Metal main with each of eight Mesa-compiled mains using one
  through eight active resources;
- padding all unused visible slots with a valid but unreferenced address;
- replacing the captured state page with a minimal 0x40-byte record whose
  first byte is `0x40`; and
- retaining only the first 0x40 bytes of the captured 0xc0-byte constant
  region, moving the Mesa main from archive offset `0x440` to `0x3c0`, and
  patching the established launch-call field; and
- shrinking the archive block to the 0x40-byte-aligned size naturally required
  by the largest 458-byte Mesa main.

As a sensitivity-positive control, relocating qword 2 to a zero page preserved
buffer addressing and most system values but made
`threadgroups_per_grid` read as zero. Restoring the 8-KiB table restored exact
output. This identifies qword 2 as helper data rather than an arena-base
requirement.

## Mesa result

Mesa now exposes one `SSBO8_SUPERSET` package ABI. Compiler-visible resources
are encoded after the three hidden carrier arguments, and Gallium builds a
fresh 0x80-byte resource record for each dispatch. Resource-count selection no
longer chooses among external launch programs.

The `superset-1` through `superset-8` regressions each compile distinct GLSL ES
3.1 source through the normal NIR and Apple9 compiler path. They use guarded
buffers, independently distinguishable inputs, a complete output oracle, and
verify that every read-only input remains byte-for-byte unchanged. All eight
passed in one EGL context/process through Gallium, the DRM UAPI, drm-shim, and
G16 hardware.

The complete 102-case direct suite subsequently reached its end and the
program-lifecycle stress passed after the constant-prefix reduction. It
reported 101 passes and one separate compiler failure in the `u2f` case. Both
the full 0xc0 and reduced 0x40 constant variants produce the same `u2f`
mismatch, so it is not caused by the constant-prefix reduction. The older
resource-count-selected wrapper was not rerun for a direct `u2f` A/B.

Relevant run logs are:

```text
/home/nsheth/Projects/asahi/logs/apple9_carrier8_relocated_hidden_table.log
/home/nsheth/Projects/asahi/logs/apple9_carrier8_active_1.log ... active_8.log
/home/nsheth/Projects/asahi/logs/apple9_carrier8_minimal_state.log
/home/nsheth/Projects/asahi/logs/apple9_carrier8_compact_block.log
/home/nsheth/Projects/asahi/logs/apple9_superset_glsl_1_to_8.log
/home/nsheth/Projects/asahi/logs/apple9_superset_full_direct_compact_constant.log
```

## Remaining boundary

This establishes a reusable carrier for up to eight visible buffers, not a
fully source-built Apple compute package. The carrier's constant and external
launch programs remain opaque development inputs, and the capacity is still
fixed at eight. Those are now independent packaging questions rather than a
per-resource-count wrapper matrix.
