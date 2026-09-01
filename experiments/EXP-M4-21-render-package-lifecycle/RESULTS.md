# EXP-M4-21: T8132 render-package lifecycle and USC aperture

## Question

Determine how native Metal handles many distinct render pipelines on G16G,
and whether ordinary pipeline switching requires a second executable archive,
a queue change, or a different USC execution base.

All shader source is caller-authored MSL in
`tools/iotrace/iohello_render_pipelines.m`.  The experiment uses public Metal
APIs and snapshots only the caller's IOKit traffic and GPU mappings.  No
proprietary executable or firmware binary was disassembled or decompiled.

## Probe

One `MTLDevice`, one `MTLCommandQueue`, and one render encoder create and use
16, 256, or 1,024 distinct fragment pipeline states.  Each fragment function
has a different ten-step ALU pattern and different constants.  Every pipeline
draws a full-screen triangle into a separate 1x1 scissor rectangle of one
shared BGRA8 target.

The M4 mini booted macOS through a freshly chainloaded `m1n1.bin` built with
`NO_DISPLAY`, under `run_guest.py`.  The guest invocation was:

```sh
IOTRACE_LOG=trace1024.log \
IOTRACE_DUMP_DIR=maps1024 \
IOTRACE_MAX_MAP=8388608 \
DYLD_INSERT_LIBRARIES=./iotrace.dylib \
./iohello_render_pipelines 1024
```

The 16-, 256-, and 1,024-pipeline runs all completed successfully.  Their
reported changed-pixel counts were exactly 16, 256, and 1,024 respectively.

## One stable executable archive

Every run has exactly one caller code mapping at GPU VA
`0x10000000000`, and that mapping is always 64 KiB:

| Pipelines | Code SHA-256 | Nonzero bytes | Last nonzero extent |
| ---: | --- | ---: | ---: |
| 16 | `ddf27f204cb0074fa0a3c165c3790247deffc7891ca60653ef78c46428d72202` | 40,001 | `0xe842` |
| 256 | `6a304ad306c444de4cf7eea567f0ab2094712af6c13dbb75f8e5512b7f09b17c` | 27,144 | `0xffa3` |
| 1,024 | `6a304ad306c444de4cf7eea567f0ab2094712af6c13dbb75f8e5512b7f09b17c` | 27,144 | `0xffa3` |

The 256- and 1,024-pipeline archives are byte-identical.  The archive is
already effectively full at 256, yet another 768 distinct pipelines execute
without changing it.  There is no second 64-KiB code mapping.

The IOKit lifecycle is also stable.  All three runs open one
`AGXAcceleratorG16G` user client and issue one selector-7 registration.  The
number of selector-9 BO registrations grows from 39 to 42 to 53, but there is
no second client/queue registration.  Thus ordinary render-pipeline switching
does not rotate the queue or publish another visible executable base.

## Where pipeline variation goes

The caller-owned state mappings grow and segment while the archive stays
fixed.  The 256-pipeline capture contains a dense `0x74000` state object and a
`0x100000` arena.  The 1,024-pipeline capture instead contains multiple
additional `0x8000` objects and larger `0x100000` arenas, including a dense
object with 420,224 nonzero bytes.

This matches the compute-side result from EXP-M4-19: Apple9 keeps a bounded,
interned template archive and puts pipeline specialization into Dynamic
Caching state and launch/resource records.  Pipeline count and source
complexity therefore do not translate one-for-one into archive programs.

## More than 4 GiB of live allocations

A second public-Metal probe, `tools/iotrace/iohello_render_usc_pressure.m`,
allocates 128-MiB private buffers before compiling and executing one render
pipeline.  Runs at exactly 4 GiB, 4 GiB plus 128 MiB, and 5 GiB test whether
ordinary VA pressure forces a new client, queue, archive address, or USC
aperture.

| Retained private storage | Code/archive DVA | Dense state DVA | State arena DVA | Result |
| ---: | ---: | ---: | ---: | --- |
| 0 | `0x10000000000` | `0x10000080000` | `0x10000138000` | complete, pixel `bf8040ff` |
| 4 GiB | `0x10000000000` | `0x10100180000` | `0x10100238000` | complete, pixel `bf8040ff` |
| 4 GiB + 128 MiB | `0x10000000000` | `0x10108188000` | `0x10108240000` | complete, pixel `bf8040ff` |
| 5 GiB | `0x10000000000` | `0x101401c0000` | `0x10140278000` | complete, pixel `bf8040ff` |

All four processes open exactly one `AGXAcceleratorG16G` client and issue one
selector-7 registration.  The code mapping remains one 64-KiB object at
`0x10000000000`; it does not move when the ordinary allocation stream crosses
the 4-GiB boundary.  In contrast, render state and arenas advance beyond the
boundary and remain usable.  Thus the USC aperture is not a general 4-GiB
limit on client BOs or a trigger for automatic queue rotation.  EXP-M4-22
further narrows its executable role: compact archive calls are aperture
relative, while full-address linked-function calls can execute code outside
the aperture.

The archive contents are not asserted byte-identical between these separate
process launches: Metal may populate a different interned template/cache
mixture.  The decisive invariants are the archive DVA, size, mapping count,
client count, and successful rendering.

## USC execution-base consequences

Separate source-side hardware probes establish the address boundary:

- Moving a complete package from `0x10000000000` to `0x10000100000`, still
  inside the same 4-GiB aperture, executes exactly.
- Moving the coherent package to `0x10100000000`, the next 4-GiB aperture,
  retires the firmware Work but executes the code still selected from the
  native aperture; the relocated output is untouched.
- Mutating the unassigned high bits of the compact launch pointer does not
  select the next aperture.
- Adding the older `0x10071` compute-base register, or the tested neighboring
  Apple9 register candidates, does not select the next aperture.
- Native G16 TA and 3D Work register arrays do not contain the M1-style
  `0x10061` and `0x10069` USC-base writes.

The evidence therefore supports a stable G16 queue/context USC aperture at
`0x10000000000`, with 32-bit-relative program addressing inside it.  More than
4 GiB of ordinary live allocation does not force macOS to change that base;
macOS instead keeps the compact template archive in the reserved aperture and
places ordinary state/resource allocations above it.  When 882 independently
addressable visible functions exhaust the archive, Metal also puts their
executable object above 4 GiB and calls it through full 64-bit code addresses;
the base still does not change.  The evidence does not yet locate the field or
initialization action that establishes the compact aperture, nor prove that
G16 hardware cannot select another one.  No public Metal API used here exposes
a way to request a different USC base.

## Driver consequence

The earlier plan to allocate a new archive generation whenever Mesa changes
stages is not native-like.  A better G16 design is:

1. Treat `usc_exec_base` as a queue-lifetime 4-GiB aperture root.
2. Maintain one immutable/interned 64-KiB template/trampoline archive at its
   base.
3. Generate per-pipeline Dynamic Caching state, launch, resource, and
   full-address executable objects.
4. Keep those objects alive through their batches and segment their ordinary
   BO arenas as necessary; they need not stay inside the USC aperture.
5. Call generated programs through their 64-bit code VAs rather than rotating
   the archive mapping or queue.

The existing DRM UAPI is therefore a plausible fit for G16: it can publish a
stable queue-level aperture even if the G16 firmware transport for that value
differs from M1.  The immediate missing implementation is native-style
Dynamic Caching package construction and its full-address executable
transition, not a UAPI extension or per-pipeline base update.

Raw traces, archive dumps, 256/1,024 mapping snapshots, and the 0/4-GiB/
4-GiB-plus-128-MiB/5-GiB pressure captures are retained under `work/`.
