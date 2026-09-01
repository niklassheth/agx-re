# EXP-M4-19: Apple9 compute-package rollover

## Question

Determine whether the apparent 27-dispatch ceiling in the source-built Mesa
package is a Metal or firmware limit, and describe how native Metal stores a
large number of bindings and pipeline states.

All captured objects belong to caller-owned Metal programs. No proprietary
binary was disassembled or decompiled.

## Probes

- `tools/iotrace/iohello_compute_bindings.m` creates one compute pipeline and
  appends many dispatches with distinct output buffers to one encoder.
- `tools/iotrace/iohello_compute_pipelines.m` runtime-compiles caller-owned
  affine kernels, creates a distinct pipeline state for each kernel, and
  switches pipeline on every dispatch in one encoder.
- `tools/iotrace/iohello_compute_archive_pressure.m` generates caller-owned
  kernels with configurable-length dependent multiply/add/xor chains. This
  prevents a large source corpus from collapsing to many copies of one tiny
  executable body.

The one-pipeline probe produced exact output at 27, 28, 32, 40, 64, 169, 170,
171, 172, 256, 1,022, 1,023, 1,024, and 1,100 dispatches. Persisted captures
through 1,024 are under `work/capture*/`; the 1,023 and 1,024 output logs end
with `exact=1`. The distinct-pipeline probe produced exact output for 44, 64,
256, 300, and 512 pipelines (`work/pipelines44`, `work/pipelines64`, and
`work/pipelines{256,300,512}`).

## Archive-call width

The apparent 32-KiB executable limit was a decoder/serializer bug, not a
Metal rollover point. The archive call is a little-endian field spanning
launch bytes `0x46..0x48`, with the measured relation

```text
call = 0x7aa + 2 * (main_offset - 0x3c0)
```

In the 256-pipeline native capture, launch index 165 uses bytes `2a ff 00` and
index 166 uses `aa 00 01`. The third byte is exactly the carry that the former
Mesa `u16` writer discarded. The native executable BO is 64 KiB; one captured
archive contains 263 linked blocks and reaches `0xffc0`. Metal therefore keeps
using one archive across the `0x8000` boundary rather than rotating its queue
or launch generation there.

## Beyond one 64-KiB archive

Metal does not put a large shader's complete operation payload into the shared
64-KiB archive. It keeps that archive fixed and grows the pipeline's
dynamic-caching state object instead.

The pressure probe executed exactly with one kernel containing 1,024, 2,048,
4,096, 8,192, 16,384, and 32,768 dependent source steps. The captures show:

| Pipelines and steps | Shared archive | Dynamic-caching state objects |
| --- | ---: | ---: |
| `1 x 16,384` | one `0x10000` BO | one `0xb0000` BO |
| `1 x 32,768` | one `0x10000` BO | one `0x160000` BO |
| `2 x 16,384/16,385` | one `0x10000` BO | `0xb0000` and `0xb4000` BOs |

All cases completed with exact GPU output. The state objects are dense,
workload-specific data and scale approximately with the operation count. In
the two-pipeline case Metal places them at distinct client VAs and both launch
wrappers retain the same shared archive. No second executable archive, queue
rotation, or archive-base switch occurs.

This is an important qualification: `0x10000` is the size of the shared
archive/template object, not a general shader-size ceiling. Dynamic Caching
makes the per-pipeline state record the scalable part of the compiler package.
The captures are under `work/overflow-{1x16384,1x32768,2x16384}`.

The behavior for overflowing the shared template archive with genuinely
different, non-internable template bodies remains unobserved. These probes
show that ordinary shader complexity does not create that condition; Metal
moves the specialization into dynamic-caching state.

## Compact launch pointers

The launch wrapper contains independent compact pointers to its resource and
dynamic-caching state records. Each pointer is:

- a 16-bit 8-KiB chunk relative to the USC executable aperture; and
- a split 13-bit byte offset within that chunk.

For the resource pointer, the in-chunk fields occupy launch bytes 1, 4, and 5,
and the chunk occupies bytes 6-7. The state pointer uses bytes 0x11, 0x14, and
0x15 plus chunk bytes 0x16-0x17. The archive call at 0x46-0x48 is a separate
relative encoding.

Repeated dispatches of one pipeline advance only the resource pointer. When
the resource address crosses an 8-KiB boundary, its low selector wraps and its
chunk increments. Distinct pipelines additionally advance the state pointer;
the observed simple-pipeline state records are 0x40 bytes with byte zero set
to 0x40 and the rest zero.

## Native Metal allocation behavior

Metal does not roll the command at 27 dispatches. Instead it segments the
underlying storage arenas independently:

- A native 0x8000-byte launch BO holds 170 0xc0-byte wrappers. Dispatch 171
  starts using a second launch BO.
- A native 0x9480-byte resource BO has a 0x14a0-byte prefix followed by 1,023
  0x20-byte binding records. Dispatch 1,024 starts a new resource generation
  and its selector restarts.
- Long direct CDM streams can also be split into separately allocated stream
  BOs while preserving one logical encoder stream.

These boundaries are storage-allocation details, not a 27-dispatch firmware
or package limit.

## Mesa failure and fix

Mesa previously treated bytes 1/4/5 as a small selector and derived bytes 6-7
from the launch wrapper address. This worked only while launch and resource
records happened to occupy corresponding chunks. With the 0xc0 launch ABI,
the first failing 60-suite item crossed the launch chunk at dispatch 43 while
its resource record remained in the previous chunk. Firmware retired the work,
but the shader saw the wrong binding and produced no output.

Mesa now constructs both compact pointers from their target addresses. It also
emits a standard 0x40 state record per dispatch and keeps compiler literals in
a separate arena, rather than aliasing them over state metadata.

Hardware validation after the fix:

- The 60-program suite runs twice with one command per pass, all 120 outputs
  exact, queue/channel/firmware counters 2/2/2, stamp 0x200, and fresh ordered
  timestamps (`logs/t8132_mesa_apple9_compact_pointer_bulk60_20260826.log`).
- A single command containing 140 repeated dispatches is exact and crosses
  both the resource and state 8-KiB chunk boundaries
  (`logs/t8132_mesa_apple9_compact_pointer_gid140_20260826.log`).

Mesa now writes all three call bytes and uses a native-sized 64-KiB queue
archive. Its focused GLES gate compiles 59 distinct programs into one archive;
the final mains are at `0x8100` and `0x8280`, whose launch calls are
`2a 02 01` and `2a 05 01`. Both 59-dispatch commands produce exact output,
the persistent queue reaches 2/2/2, the firmware stamp reaches 0x200, and the
timestamp intervals are fresh and ordered
(`logs/t8132_mesa_apple9_archive_u17_crossing_20260826.log`).

Mesa's current 1-MiB package reserves 0x50000 bytes for launch wrappers, so it
uses a conservative 1,280-dispatch command limit based on the largest known
0x100-byte wrapper. Reaching that limit starts another ordinary command; it is
not a hardware limit and is independent of Metal's native arena sizes.
