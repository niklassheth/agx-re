# EXP-M4-37 results: Apple9 32-bit literals

Date: 2026-09-01
Target: T8132 / Apple M4 / macOS 26.6.2 build 25G83

All native programs in this experiment were compiled from the MSL sources in
`kernels/`. Only their serialized archives and `_agc.main` regions were
inspected. No Apple binary was disassembled.

## Scalar mode-2 form

Mode 2 is an eight-byte untyped 32-bit literal write. Integer and floating-point
constants use the same encoding; only their raw payload bits differ.

For destination `d` in r0..r63, native modifier bit `m`, and raw value `v`:

```text
b0 = ((d & 0x0f) << 4) | 0x0c
b1 = 0x80 | (v & 0x7f)
b2 = ((d >> 4) << 6) | (m << 5) | 0x02
b3 = (v >> 24) & 0xfe
b4 = (v >> 6) & 0x1e
b5 = (v >> 9) & 0x0c
b6 = (v >> 13) & 0xff
b7 = (v >> 21) & 0x0f
```

`kernels/literal_bits.metal` supplies a base value and every one-bit payload
difference. The 33 extracted programs recover all 32 payload bits, and all 33
executed against exact full-output CPU oracles.

The complete destination rule is:

```text
dst = (b0 >> 4) | ((b2 & 0xc0) >> 2)
```

Thus byte 0 supplies destination bits 0..3 and byte 2 bits 6..7 supply bits
4..5.  The form reaches exactly r0..r63.  The earlier seven-bit interpretation
was off by one: it treated byte 2 bits 5..7 as three destination bits.

A separated producer/consumer cross established the corrected map directly:

- All 48 combinations of byte-2 leader nibble 0..15 with low destination
  nibbles 0, 2, and 15 wrote the exact `0x12345678` value to the destination
  predicted by the formula.  This covers r0/r2/r15, r16/r18/r31,
  r32/r34/r47, and r48/r50/r63.
- For a fixed low nibble of 2, leader nibbles 0..3 wrote r2, 4..7 wrote r18,
  8..11 wrote r34, and 12..15 wrote r50.  Reading every r0..r15 after the
  same records showed no redirected low-register write.
- Preseeding r2 with 7 showed that a record targeting a higher bank preserves
  r2; the prior zero result was a read of the wrong register, not a suppressed
  literal.
- Independently writing and reading high GPRs with IADD had already shown that
  the consumer could address them.  The defect was solely the literal packer's
  destination-bit placement.

Byte 2 bit 4 is zero in every native record selected by the payload signature.
Bit 5 occurs in both states.  Exhaustively toggling both bits across all four
destination banks and three low destination nibbles left the destination and
the complete 32-bit value unchanged.  They are therefore not destination bits;
bit 4 is a native-zero modifier and bit 5 is an output-inert scheduling or
lifecycle modifier in this carrier.  Its unrestricted semantic name remains
open.

The corpus distribution follows the destination-bank interpretation rather
than an unrelated opcode split.  The four banks contain 783, 273, 208, and 10
payload-shaped native records respectively, with the highest bank confined to
the largest ray-query programs.  Metal emits only even byte-2 leader nibbles:
bit 4 is always zero, while bit 5 selects the two native variants within each
bank.

Native Metal uses mode 2 for `literal_store`. For the same `0x12345678` value
used twice by `literal_alu`, Metal emits ALU immediate operand descriptors and
does not emit mode 3. This rules out the earlier model of mode 3 as a generic
long scalar literal.

## Mode-3 form

Mode 3 retains the same literal payload layout in the first eight bytes and
adds a two-byte publication record.  Its destination/publication mapping must
not inherit the disproven scalar mode-2 byte-2 extension. The bounded facts are:

- Extended destinations use byte 8 with `(b8 & 0x7e) == 0x40`; low
  destinations use `(b8 & 0x7e) == 0`.
- Byte 9's high three bits take the six native values 0 through 5. The low five
  bits are zero in the valid corpus forms.
- Every scalar lane contributing to one native texture/output tuple carries
  the same byte-9 tag.
- In `pressure0` through `pressure6`, Metal schedules the two constant texture
  coordinates first and gives both tag 0. Later outstanding device loads do
  not retroactively change it.
- A native 2D texture write has two preceding live system-value producers and
  tags its four literal data lanes with 2. Native 3D and 2D-array writes have
  three such producers and tag all four lanes with 3.
- Across 151 structurally valid mode-3 records in the unified corpus, tags
  0..5 occur 14, 17, 28, 29, 51, and 12 times respectively.

This is the same shape as a pending producer-group allocation: the first group
uses code 0, subsequent live groups advance through codes 1..5, and an n-ary
consumer receives one shared tag for the complete tuple. It also explains why
a synchronous-looking literal can participate: the scoreboarding mechanism is
tracking publication from a non-ALU producer path, not merely memory latency.
Code 0 aligns with the independently recovered first scoreboard allocation,
physical slot 6; codes 1..5 align naturally with slots 1..5.

That last mapping is the best current structural model, not yet an unrestricted
emitter contract. In particular, byte-9 mutations were output-inert in the
long vertex pressure carrier, so the tag can behave as a scheduling/lifecycle
hint when enough independent work separates publication and consumption.
Mode 3 should be represented as a pending tuple producer when texture/output
lowering is implemented, rather than exposed as a generic scalar `MOV_IMM32`.

## Mesa consequence

Mesa now encodes scalar mode-2 `MOV_IMM32` with `(dst >> 4) << 6`, uses the
proven native-zero bit-5 variant, and accepts the complete encodable
destination range r0..r63.  Destinations r64 and above are rejected.  The
machine destination class is no longer restricted to r0..r15, so ordinary
register allocation can place literals in all four proven banks.  Mode 3 is
not emitted by the current scalar compute compiler.

Host-side packer and compiler tests exercise r0, r18, r34, and r63, reject
r64, and verify that an ordinary compiled shader allocates literals above
r15.  The Apple9 unit subset passes 70/70 and the complete Asahi compiler test
binary passes 124/124.  No additional device execution was performed for this
compiler change; it relies on the retained T8132 hardware evidence below.

Validation completed on T8132:

- A 128-case scalar-literal/FADD cross covered both modifier-bit states,
  scoreboard routes 0..7, and both FADD source roles with exact output.
- A 256-case destination probe crossed all 16 byte-2 leader nibbles with reads
  from every low GPR. A separate 16-case preseed probe distinguished a
  higher-bank write from a suppressed write.
- The final 48-case map crossed all four destination banks, both modifier
  bits, both bit-4 states, and low destination nibbles 0, 2, and 15. Every
  result matched the six-bit destination formula and exact literal payload.
- 69 Apple9 compiler/packer/allocator tests passed.
- The formerly failing `gid + 0x12345678` shader passed two complete
  16,384-word exact-output submissions.
- The single-boot general compute corpus passed its first 37 workloads,
  including constant32, sparse constant32, MAD, integer DAG, pressure, add,
  subtract, multiply, and all logic cases. It then reached the existing U2F
  conversion failure, whose generated program contains no literal instruction.
- The 11-workload add3 bring-up suite passed exact output in one boot, including
  vector load/store and scoreboard-pressure cases.

## Artifacts

- `kernels/literal_bits.metal`: one-bit payload basis.
- `kernels/slot_pressure.metal`: scalar store, scalar ALU, atomic, and pending
  pressure sources.
- `kernels/mode3.metal`: texture and vertex tuple carriers.
- `make_*_variants.py` and `run_*_variants.py`: fixed-size archive mutations
  and full-output hardware runners.
- `work/native-scalar/` and `work/native-pressure/`: local own-source archives
  and extracted mains. These are research run products, not production Mesa
  dependencies.
