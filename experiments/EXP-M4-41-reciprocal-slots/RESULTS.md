# EXP-M4-41 results: accurate reciprocal and source handoff

> **Superseded field interpretation:** EXP-M4-42 establishes that instruction
> bits 12--17 are a six-bit pending-slot dependency mask shared with conversion,
> integer-ALU, shift, bit-count, and bitfield forms.  In particular, byte 2
> `0x54` is mask zero and `0x56` is slot-6 dependency, not a generic boolean
> handoff enable.  EXP-M4-41's producer-only retags left the consumer at slot 6
> and were not a sensitivity-positive slot cross; the coordinated 6x6 crosses
> in EXP-M4-42 supersede that conclusion.  Reciprocal opcode, precision, result
> descriptor, and source-release findings below remain valid.

## Result

Apple9's accurate scalar reciprocal is the ten-byte `fspecial` form:

```text
af 00 56 00 02 00 10 48 20 00
```

For the canonical FP32 form:

```text
byte 0 bit 7       function-family bit (set for reciprocal)
byte 1 low nibble  function class 0
bits 12--17        six-bit pending-slot dependency mask (EXP-M4-42)
byte 3             destination descriptor, dst = byte >> 1
byte 4 bit 1       result-valid/publication enable
byte 5             source descriptor, src = byte >> 2
byte 6 bit 4       release source on this use
byte 7             0x48 FP32 reciprocal datapath
byte 8             0x20 reciprocal precision/control
byte 9             0x00 in every observed reciprocal
```

The important correction is that byte 6 value `0x10` is not the reciprocal
opcode by itself. Native Metal emits both `0x00` and `0x10` for the same
arithmetic operation. Bit 4 is the source last-use/release control.

## Native corpus

`analyze_corpus.py` walked 35,341 public-source Metal archives containing
30,569 unique stage mains. It found 1,179 unique accurate reciprocal
instructions after accepting both source-retain and source-release forms:

| Field | Native values |
|---|---:|
| byte 2 low mask bits | `0x54`: 1,146; `0x56`: 33 |
| byte 4 result descriptor | `0x02`: 41; `0x03`: 1,138 |
| byte 6 source lifetime | retain `0x00`: 85; release `0x10`: 1,094 |
| byte 7 | `0x48`: 1,179 |
| byte 8 | `0x20`: 1,168; `0x60`: 11 |
| byte 9 | `0x00`: 1,179 |

Byte 1's high nibble is zero in 1,176 cases and takes values 1, 2, and 4 once
each in one high-pressure unrolled solver.  EXP-M4-42 identifies those values
as the slot-1, slot-2, and slot-3 dependency bits.  Their earlier apparent
inertness came from sweeping consumers whose ordinary GPR value was already
durable, rather than coordinating a still-pending producer with the consumer.

## Source handoff and scoreboard relationship

EXP-M4-42 supersedes the original boolean interpretation.  Reciprocal carries
the shared six-bit pending-slot dependency mask in instruction bits 12--17:

- `0x54` has an empty dependency mask;
- `0x56` waits for pending slot 6; and
- the byte-1 high nibble holds the slot-1 through slot-4 mask bits.

An ordinary GPR source remains readable with any mask once it is durable.  The
earlier ALU-source mutation therefore established fallback behavior, not a
generic `0x56` enable mode.

Clearing the slot-6 dependency (`0x56 -> 0x54`) immediately after a device load
changed `1/x` into positive infinity for every lane: the ordinary GPR path still
held zero. Conversely, adding a slot-6 dependency to an already durable
ALU-produced source preserved both the reciprocal result and a separate pending
load group.

The producer-only retags in this experiment did not update the matching
consumer bit and were not a valid slot test.  EXP-M4-42 performs the complete
producer-token/consumer-mask cross: reciprocal works for all six slots exactly
when the corresponding mask bit is present, fails for every neighboring bit,
and remains exact when unrelated bits are added.

## Source lifetime

The source release control is independent of the handoff:

- Native `rcp_source_reuse` emits byte 6 `0x00`. It computes `1/x`, retains
  `x`, and a later ALU reads `x` correctly.
- Changing only byte 6 to `0x10` leaves `1/x` exact but makes the later ALU
  observe zero for `x`.
- Changing a dead-source reciprocal from `0x10` to `0x00` leaves its output
  exact.

This matches the established Apple9 last-use model: release is semantic
register lifetime state, not part of reciprocal selection and not a mere
scheduler hint.

## Result descriptor

Byte 4 was previously called a source class. The controlled cases refute that
name: identical FP32 sources use `0x02` when the reciprocal result goes to a
store and `0x03` when it feeds another ALU operation.

Hardware establishes only the following safe subset:

- bit 1 is required; clearing it (`2 -> 0` or `3 -> 1`) makes the result zero;
- bit 0 can be toggled both ways without changing low-pressure store, ALU, or
  two-consumer fanout outputs.

Metal's bit-0 choice is therefore retained as a native result-use hint, but it
is not assigned stronger semantics yet.

## Reciprocal accuracy

The unmodified native instruction was executed for all FP32 denominators
`D = 1..1024`. The worst observed error was:

```text
max |D * r - 1| = 7.136259227991104e-08
at D = 981, r = 0.0010193680645897985
```

That is about 23.74 effective bits and satisfies `|D*r - 1| <= 2^-18` with
substantial margin. It is sufficient for the proposed corrected FP32
ceiling-division lowering over the current grid/workgroup domain without a
Newton refinement.

## Compiler rule

For the initial reciprocal emitter:

1. Use the ten-byte accurate `fspecial`, not the six-byte estimate seed.
2. Encode the allocated destination and source GPRs normally.
3. Emit the union of the pending source groups' slot bits in instruction bits
   12--17; use mask zero for fully durable sources.
4. Set byte 6 bit 4 exactly when the source dies at this instruction.
5. Preserve Metal's result-descriptor choice (`0x02` for the direct-store
   shape and `0x03` for an ALU consumer) until its bit 0 is understood.
6. Treat source last-use independently from the pending-slot mask.

Exact structured measurements are in `HARDWARE_RESULTS.json`; all captured
archives were compiled from `kernels/reciprocal_slots.metal`.
