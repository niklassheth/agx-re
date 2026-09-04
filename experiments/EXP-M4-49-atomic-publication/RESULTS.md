# EXP-M4-49: Apple9 atomic-result publication

## Scope

This experiment isolates the destination and scoreboard-publication fields of
the eight-byte record immediately following a returning device atomic.  The
tests use shaders compiled from our own GLSL and execute on T8132 through the
G16 DRM shim.  Both the returned atomic value and the final atomic target are
checked against exact CPU oracles.

## Result destination

The result-record destination is a six-bit GPR number:

```text
byte0 = ((dst & 0x0f) << 4) | 0x0c
byte2 = 0x09 | ((dst >> 4) << 6)

dst = (byte0 >> 4) | ((byte2 >> 6) << 4)
```

Every destination from `r0` through `r63` passed.  Each case used 256 lanes
with distinguishable input and output values and checked the atomic side
effect separately.  The run also crossed the shim's physical queue rollover
at publication 33 without changing the result.

This disproves the previous `r0` or `r0..r15` result-bank restriction.  The
record cannot encode `r64` or above with this layout.

## Scoreboard publication

The result record uses `byte5[7:5]` as a compact three-bit publication code:

| Logical slot | Code | `byte5` |
|---:|---:|---:|
| 6 | `001` | `0x20` |
| 1 | `010` | `0x40` |
| 2 | `100` | `0x80` |
| 3 | `011` | `0x60` |
| 4 | `101` | `0xa0` |
| 5 | `110` | `0xc0` |

The first three codes are present in native own-source Metal programs.  The
remaining three were established by one hardware shader that issued six
returned atomics before consuming them.  The six results used slots
`6,1,2,3,4,5`, landed in distinct GPRs, received different XOR tags, and were
combined by an ordered weighted recurrence.  All six returned values and the
final target value matched exactly.  The complete test passed twice in the
same cold boot and once in a preceding boot.

Code `111` remains unassigned.  It is not evidence for a seventh slot.

## Important correction: the atomic packet's six bits

The six variable bits at atomic-packet bits 12--17 are not the returned-result
slot selector.  Treating them as a six-bit one-hot output-slot field preserved
the atomic memory side effects but made the results assigned to slots 3--5
read as zero.  Keeping the atomic packet at the native ordinary-input value
while changing the adjacent result record produced exact results in all six
slots.

EXP-M4-50 subsequently closed those packet bits as a six-bit one-hot input
dependency mask. They must not be tied to the output-slot allocator: ordinary
materialized inputs use mask zero, while a directly pending input names its
actual producer slot.

Likewise, forcing a single first atomic into slot 1--5 failed while slot 6
passed.  That is consistent with slot allocation being scheduled state: an
isolated first returned atomic uses the preferred first slot 6, while later
simultaneously pending results may use the remaining free slots.

## Compiler consequence

It is now safe to model the publication record with:

- an allocatable six-bit result destination (`r0..r63`); and
- scheduled scoreboard slots 1--6 using the code table above.

Relaxing the compiler still requires integrating returned atomics into the
normal scoreboard allocator.  It is not correct to expose a knob that assigns
an arbitrary slot independently of issue order and pending lifetimes.

## Raw evidence

- [`raw/final-positive.log`](raw/final-positive.log): all 64 destinations,
  followed by two exact all-slot executions in one boot.
- [`raw/all-slots-three-bit.log`](raw/all-slots-three-bit.log): independent
  exact all-slot execution.
- [`raw/result-field-slots.log`](raw/result-field-slots.log): negative result
  from the rejected six-bit one-hot output-slot hypothesis.
- [`raw/slots.log`](raw/slots.log): isolated forced-slot experiment showing
  why slot assignment must follow a valid pending-result schedule.
