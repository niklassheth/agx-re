# EXP-M4-23 results: two command queues in one G16 client VM

## Question

Does public Metal permit one `MTLDevice`/client VM to own two command queues,
and how does the G16 macOS userspace/kernel interface represent them?

## Method

`iohello_compute_two_queues.m` creates one `MTLDevice`, two distinct
`MTLCommandQueue` objects, one runtime-compiled pipeline, and one shared output
buffer.  It submits `q0`, `q1`, then `q0` serially.  It then commits one command
from each queue before waiting for either.  Every command writes a different
word of the same output buffer.

The run used the clean-room iotrace interposer and per-stage caller-BO
snapshots.  It was run on T8132 under a freshly chainloaded NO_DISPLAY m1n1 and
the exact release XNU guest path.

## Result

Yes.  Both queues and all five command buffers completed successfully.  The
shared output was exact:

```
TWO_QUEUE_RESULT complete=1 exact=1 \
  words=11111111,22222222,33333333,44444444,55555555,00000000,00000000,00000000
```

This includes two commands, one from each queue, committed before either wait.
It proves coexistence and shared-resource correctness; it does not claim an
ordering guarantee between different queues.

## Driver representation

The process opens exactly one `AGXAcceleratorG16G` user client (`conn=2203`).
Both command queues are registered through that same connection:

| Metal queue | selector-7 returned identity | selector-16 returned mapping / identity | selector-28 arguments |
| --- | --- | --- | --- |
| `q0` | `1`, token `0x700007d60` | `0x10708c000`, `1` | `[1, 1]` |
| `q1` | `2`, token `0x700007d75` | `0x1070f0000`, `2` | `[2, 2]` |

The two 1040-byte selector-7 registration inputs are otherwise byte-identical.
At teardown macOS destroys identities 2 and 1 independently through paired
selector-8/selector-17 calls.  Therefore these are two real driver queue
objects with independent identities and lifecycles, not two Objective-C
wrappers around one queue.

The caller resource namespace is shared:

- Both queues consume the same pipeline and write the same buffer.
- There is one AGX user-client connection and one selector-9 GPU-VA namespace.
- The executable archive remains at `0x10000000000`; after the first dispatch
  its bytes/hash stay unchanged through submissions on both queues.
- Serial submissions reuse the same caller command-package allocation set.
  When two commands are simultaneously in flight, Metal allocates a second
  package set rather than overwriting the first.

The active mapped completion page also accumulates distinct completion values
from the two queues.  This is consistent with queue-private submission
identities feeding a shared client completion facility.

## Conclusions

1. Multiple `MTLCommandQueue` objects per device/VM are supported on G16.
2. macOS creates a distinct driver queue identity for each one, while client
   mappings, resources, pipeline code, and the USC archive namespace remain
   shared.
3. Queue-local ordering remains independent.  Applications need explicit
   synchronization for cross-queue dependencies; this experiment used
   disjoint output words for the simultaneous commands.
4. A second queue does **not** create a second VM or a second logical
   `usc_exec_base` aperture.  It therefore does not by itself permit two
   different BOs to occupy the same DVA concurrently.  It is useful for
   independent scheduling and in-flight package ownership, not as an address
   aliasing mechanism.

The trace proves separate driver-facing queue identities.  Correlating each
identity to its exact firmware-private `0xfffffc...` queue object would require
a held hypervisor snapshot and is deliberately left as a narrower follow-up;
it is not needed for the conclusions above.
