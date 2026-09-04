# EXP-M4-50: Apple9 device-atomic input dependency

## Scope

This experiment isolates bits 12--17 of the 14-byte per-lane device-atomic
packet. All hardware programs were generated from our own GLSL and executed on
T8132 through the G16 DRM shim. Every case checked the complete output and
atomic target buffers against independent CPU oracles.

## Encoding

The field is one six-bit dependency mask spanning two bytes:

```text
mask = ((byte1 >> 4) & 0x0f) | ((byte2 & 0x03) << 4)
```

Consequently:

```text
67 01 54 ...  mask 0x00: ordinary/materialized GPR inputs
67 11 54 ...  mask 0x01: dependency on slot 1
67 01 56 ...  mask 0x20: dependency on slot 6
```

`0x56` is not a separate direct-addressing form. It is the common `0x54`
framing with the slot-6 dependency bit in byte 2.

## Hardware proof

The first sweep assigned a direct pending device load to slot 6 and fed its
value to a discarded atomic. All 64 masks were executed over 256 lanes:

- all 32 masks containing bit 5 produced exact output and target buffers;
- all 32 masks lacking bit 5 left all 256 target words incorrect; and
- materialized-input controls were exact with masks `0x00`, `0x01`, `0x20`,
  `0x21`, and `0x3f`.

The second sweep repeated the experiment for producer slots 1 through 6 over
16,384 lanes per case. For every slot it tested mask zero, a wrong adjacent
bit, the exact producer bit, and the producer bit plus the wrong bit:

- zero and wrong-only masks failed all 16,384 atomic target words;
- exact and exact-plus-idle masks matched every word; and
- the independent output canary matched in every case.

This proves that the field is an input dependency mask, that every established
slot has the corresponding one-hot bit, and that an extra idle bit is harmless
in these controlled cases. It does not prove that waiting on an occupied but
unrelated slot is semantically harmless.

## Native-corpus cross-check

The own-source `k_atomics` shader contains two especially clear direct cases:

```text
device_load @ 0x188
atomic exchange @ 0x196: 67 01 56 ...  dependency slot 6

device_load @ 0x1a4
compare-exchange @ 0x1b2: 67 01 56 ...  dependency slot 6
```

Its earlier reduction/materialized atomics use `67 01 54`, or mask zero. The
native code and controlled mutations therefore agree.

## Correction to the Mesa model

Mesa had incorrectly promoted `0b 00 00 02` to an unconditional
`DEVICE_ATOMIC_PREP` pseudo. The native corpus does not establish that record
as atomic framing: it occurs before a subset of returned atomics whose packets
also wait on slot 1, while materialized-input atomics can execute without it.

The bad pseudo explained an otherwise misleading regression:

- emitting `0b 00 00 02` with mask zero caused intermittent missing returned
  values in a 16,384-lane, ten-operation atomic program;
- adding a synthetic slot-1 dependency made that program pass, but only hid
  the bad record behind a wait; and
- removing the pseudo while retaining mask zero made the complete atomic suite
  exact.

The corrected compiler therefore emits no invented atomic-prep instruction.
Ordinary GPR inputs use mask zero. A direct pending input must name its actual
producer slot. Returned-result slot allocation remains independent and lives
in the adjacent eight-byte publication record.

## Validation

After the correction, one cold-boot run passed both `device-atomic-native-shape`
and the complete `device-atomics` suite. The latter covers every supported
integer operation, returned and discarded results, compare-exchange,
contention, divergent loops, 4,096 exact private recurrences, and 32 repeated
dispatches. Eight hardware submissions completed with exact output oracles.

## Raw evidence

- [`raw/mask-sweep.log`](raw/mask-sweep.log): complete slot-6 mask sweep and
  materialized controls.
- [`raw/all-input-slots-final.log`](raw/all-input-slots-final.log): valid
  all-six-slot, 16,384-lane sweep.
- [`raw/compiler-regression.log`](raw/compiler-regression.log) and
  [`raw/compiler-trace.log`](raw/compiler-trace.log): failures caused by the
  bogus prep record with mask zero.
- [`raw/final-regression.log`](raw/final-regression.log): temporary synthetic
  slot-1 wait that hid the problem; retained as negative design evidence.
- [`raw/no-prep-common-slot-regression.log`](raw/no-prep-common-slot-regression.log):
  first exact compiler and hardware regression without the bogus prep record.
- [`raw/final-cleanup-regression.log`](raw/final-cleanup-regression.log): final
  cold-boot regression after removing the dead prep opcode and machine form.

`raw/all-input-slots.log`, `raw/all-input-slots-large.log`, and
`raw/all-input-slots-trace.log` are diagnostic attempts in which an experiment
override was applied before the normal packer and overwritten, or the GPU was
not cold. They are not result evidence.
