# EXP-M4-43 results: F2I is a ten-byte conversion form

## Verdict

The stream-framing asymmetry is real on T8132:

- 32-bit integer-to-float is an eight-byte conversion form.
- 32-bit float-to-integer is an eight-byte core plus a two-byte result
  descriptor/continuation, and therefore occupies ten bytes in the stream.

The last two F2I bytes are not a separately decoded compact instruction.

## Native framing

The two own-source Metal kernels differ only in conversion direction and have
the same surrounding `get_sr`, `device_load`, `device_store`, and `stop` shape.

```text
I2F main, 44 bytes:
  0000  1ca01006                              get_sr
  0004  6710440001012000510100404600          device_load
  0012  a70756000200ac60                      i2f, 8 bytes
  001a  e700540000012100110000901100          device_store
  0028  0e000000                              stop

F2U main, 46 bytes:
  0000  1ca01006                              get_sr
  0004  6710440001012000510100404600          device_load
  0012  270756000200b4080200                  f2u, 10 bytes
  001c  e700540000012100110000901100          device_store
  002a  0e000000                              stop
```

The two-byte size difference is exactly at the conversion; the following
known device-store and stop records retain their complete lengths.

## Executable boundary discriminator

The disputed native F2U suffix is `02 00`.  It was replaced in place with
three independently established compact `mov_imm r0, imm` encodings and one
`mov_imm r15, 0` encoding.  If decode restarted after an eight-byte F2U core,
the first three cases would overwrite the value stored from r0 with 7, 42, or
99.  None did:

| bytes at F2U +8 | interpretation if independent | observed output |
|---|---|---|
| `02 00` | native | `1, 2, 3, 65535` |
| `03 00` | alternate continuation | `1, 2, 3, 65535` |
| `0c 07` | `mov_imm r0, 7` | `1, 2, 4, 65535` |
| `0c 2a` | `mov_imm r0, 42` | `1, 2, 4, 65535` |
| `0c 63` | `mov_imm r0, 99` | `1, 2, 4, 65535` |
| `fc 00` | `mov_imm r15, 0` | `1, 2, 4, 65535` |

Every command completed, each interleaved native control remained exact, and
no replacement produced its compact-move oracle.  Instead, every byte-8 value
whose low bit pair lacked bit 1 changed conversion of 3.75 from 3 to 4.  The
hardware therefore consumes byte +8 as conversion metadata.

## What the continuation carries

With the established signed-I32 selector in byte +7 (`0x48`), the low two bits
of byte +8 have independent, observable effects:

| byte +8 | inputs `-1.25, -2.5, 3.75, -65535.75` |
|---|---|
| `0x00` | `255, 254, 4, 128` |
| `0x01` | `-1, -2, 4, -65536` |
| `0x02` | `255, 254, 3, 128` |
| `0x03` | `-1, -2, 3, -65535` |

The rounding interpretation of bit 1 is exact in this FP32 conversion
envelope.  A tie panel gives:

```text
byte8 = 0x01:  2.5, 3.5, -2.5, -3.5 -> 2, 4, -2, -4  (RTE)
byte8 = 0x03:  2.5, 3.5, -2.5, -3.5 -> 2, 3, -2, -3  (RTZ)
```

Thus byte +8 bit 1 selects RTE when clear and RTZ when set for this form.  Bit
0 participates with byte +7 in the destination integer format/sign/saturation
descriptor.  The two native 32-bit cast recipes are:

```text
F32 -> U32 RTZ: byte7 = 0x08, byte8 = 0x02
F32 -> S32 RTZ: byte7 = 0x48, byte8 = 0x03
```

Large-value and negative inputs reproduce the expected U32 and saturating S32
results for those two native pairs.  Crossed pairs select other narrow or
saturating behavior; this experiment does not assign final names to them.

Byte +9 remains reserved/inert in the broad envelopes tested by EXP-0184 and
EXP-0202.  Inert does not make it a separate instruction: it is the second byte
of the conversion continuation word.

## Why the directions differ

This is an encoding asymmetry, not evidence for different arithmetic units or
latencies.  Float-to-integer needs an explicit integer-result descriptor and a
selectable rounding mode.  Apple9 places those controls in the trailing word.
For the observed integer-to-float form, the source integer class/sign fits in
the eight-byte core and rounding is the fixed native RTE behavior, so no
trailing result word is emitted.

The architectural motivation for choosing this particular variable-length
layout is not observable.  The stream contract and the live purpose of the
extra byte are observable and hardware-proven.

## Evidence

- `HARDWARE_RESULTS.json`: native controls and compact-instruction boundary
  discriminators.
- `SIGNED_RESULTS.json`: byte-8 low-bit, rounding-tie, and destination-type
  crosses.
- Target: T8132 Apple M4, macOS 26.6.2 build 25G83.
- Provenance: own-source Metal + hardware mutation only; no proprietary Apple
  binary inspection.
