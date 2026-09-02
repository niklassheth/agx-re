# Results

## Bottom line

The split register-field architecture is real and highly symmetric for the
ordinary ALU families tested.  Mesa's current split-bit formulas for FMA,
integer logic, and ISELECT are correct over the tested r0..r95 range.  The same
architecture is now hardware-proven for compact FALU2, its 8-byte and 10-byte
extensions, integer min/max, and native half ALU.  The
older “descriptor 64..127 aliases modulo 64” observation is also correct, but
it describes only the descriptor byte with the separate high bit held clear.
It is not the full operand encoding.

`get_sr` is the exception.  Its byte-3 high bits are not destination bits, and
Mesa's current formula cannot distinguish the requested destinations.

## Independent observer gate

The generated memory-transfer harness completed 144 positive r0..r95 transfer
cases, two intentional negative controls, and eight slot-discovery probes with
no hang.  This establishes that the split-field tests do not depend on a
compiler-assigned register dump or on the instruction being tested to observe
its own result.

## Descriptor-only controls

The exhaustive G16 runs reproduce the earlier G17 behavior exactly:

- ISELECT: 512 source-descriptor cases plus 16 compact destinations pass.
- integer logic: 256 source-descriptor cases plus 16 compact destinations pass.
- FMA: 384 source-descriptor cases plus 16 compact destinations pass.

For all three families, descriptor values naming 64..127 without setting the
separate high bit read the corresponding r0..r63 value.  These are controls for
the split-bit experiment, not evidence against it.

## FMA

The complete register number is split as Mesa currently encodes it:

- destination bits 0..3: byte 0 high nibble;
- destination bits 4..5: instruction bits 22..23;
- destination bit 6: instruction bit 60;
- source A bit 6: instruction bit 56;
- source B bit 6: instruction bit 58;
- source C bit 6: instruction bit 38.

Eleven destination probes cover r0 and boundaries through r95.  Every non-low
destination writes the requested high register while leaving the low-nibble
alias unchanged.  Thirty-six source probes cover all three roles; the twelve
decisive r64..r95 probes all read the high physical register rather than its
modulo-64 alias.  There were no faults or hangs.

For example, changing the r0 destination FMA
`09 05 06 07 01 08 02 c0` to the exact r64 form
`09 05 06 07 01 08 02 d0` moves the result to r64.  It does not change the
arithmetic operation.

This explains why an older one-dimensional sweep called FMA op-byte bits 6/7
“silent corruptors”: the readback watched the old low destination, while those
bits had actually moved the result to a different destination bank.

## Compact two-source ALUs

Five forms were tested with a common coupled matrix:

- six-byte FP32 FALU2;
- eight-byte saturating FALU2;
- ten-byte source-modifier FALU2;
- six-byte integer min/max;
- six-byte native half ALU.

Each form ran 31 cases: seven destination cases and twelve cases for each of
the two source roles.  Seventeen are low-bank controls.  The fourteen decisive
cases comprise six high destinations and four high registers in each source
role.  All 155 cases completed with exact outputs, zero faults, and zero hangs.

All five forms use the same complete register map:

- destination bits 0..3: byte 0 high nibble;
- destination bits 4..5: instruction bits 22..23;
- destination bit 6: instruction bit 44;
- source A bits 0..5: instruction bits 9..14;
- source A bit 6: instruction bit 40;
- source B bits 0..5: instruction bits 25..30;
- source B bit 6: instruction bit 42.

This directly corrects the current FALU2 interpretation.  In its GPR form:

- bit 40 is source A register bit 6, not an alternate zero-valued source class;
- bit 42 is source B register bit 6, not a second generic source-class bit;
- bit 44 is destination register bit 6, not a no-write/corruption control;
- bits 22..23 are destination bits 4..5, not silent corruptors;
- descriptor bits 15 and 31 are not register bit 6.

Bit 41 remains the independently demonstrated source-B non-GPR-file selector.
Its interaction with source-B bit 6 is the existing uniform-versus-inline-
immediate overload and is not contradicted by the GPR probes.

The old accepted-value sets now have a simple interpretation.  The eight even
values formerly called `FALU2_MODHI_OK_ALU` are destination bit 6 clear plus
scoreboard slots 0 through 7.  The direct-load value `0xc` is destination bit 6
clear plus scoreboard slot 6.  It was never an opaque provenance modifier.

The earlier “source class reads zero” controls are also explained: setting bit
40 or bit 42 while only r0..r63 were seeded selected an unwritten r64..r127
source.  Coupled tests that seed rN and rN+64 differently select the high value
in every decisive case.

Native half ALU follows the same register-bank map at half-register granularity.
When the selected low half is last-used, that half clears while the high half
of the physical register remains intact.  This lifetime detail changed only a
secondary oracle; all computed destination values and bank selections were
exact in both runs.

## Integer logic

The same split architecture holds:

- destination bits 4..5: instruction bits 22..23;
- destination bit 6: instruction bit 44;
- source A bit 6: instruction bit 40;
- source B bit 6: instruction bit 42.

All ten non-low destination probes through r95 land in the requested register.
All eight decisive high-source probes read r64..r95 rather than r0..r31.  The
two low destination controls and sixteen low-source controls also behave as
expected.  No case faults or hangs.

## ISELECT

The four source roles use the same split-bit pattern as the corresponding FMA
operand positions:

- compare A bit 6: instruction bit 56;
- compare B bit 6: instruction bit 58;
- selected-true bit 6: instruction bit 38;
- selected-false bit 6: instruction bit 70.

All sixteen decisive r64..r95 cases select or compare the high physical
register.  All thirty-two low controls behave as expected.  ISELECT's
destination remains the compact byte-0 nibble in the tested form.

## `get_sr`

The exact current Mesa encodings were installed into EXP-0207's compiled
`sr_dump` carrier so its established downstream publication sequence and
disjoint codeword readback remained intact.

| requested destination | exact bytes | result |
|---:|---|---|
| r0 | `04 82 10 06` | baseline, no codeword clobber |
| r16 | `04 82 10 26` | byte-identical output to r0, no clobber |
| r32 | `04 82 10 46` | byte-identical output to r0, no clobber |
| r48 | `04 82 10 66` | byte-identical output to r0, no clobber |
| r64 | `04 82 50 86` | alternate behavior, codeword slot 8 clobbered |
| r80 | `04 82 50 a6` | byte-identical output to r64, slot 8 clobbered |

Therefore byte 3 bits 5..7 are inert in both datapath modes tested.  They do
not encode destination bits 4..6.  `dp_width=0x50` selects an alternate
destination/publication bank, but r64 and r80 still collapse to the same
behavior.  The current Mesa `get_sr` destination formula is not general:

- r16/r32/r48 collapse to the low-nibble destination;
- r64 and r80 collapse to the same alternate target;
- the exact mapping and publication contract of `dp_width=0x50` still need a
  dedicated model before high-register `get_sr` can be emitted safely.

Generated bare programs were not used to promote a `get_sr` conclusion: a
naive following store or logic operation does not consume its result as a
durable ordinary GPR.  That negative result is consistent with a distinct
publication/lifetime path and is why the exact-pair test deliberately retains
Metal's known-good downstream sequence.

## Compiler consequences

- Keep and document the existing split high bits for FMA, logic, and ISELECT.
- Add the same split map to FALU2, its extended forms, min/max, and half ALU.
- Replace FALU2's multi-bit `srcA_class`/`srcB_class`/`mod_hi` abstraction with
  explicit register extensions, the source-B file selector, and scoreboard
  slot fields.
- Correct the register metadata and old documentation that currently says
  these forms stop at r63 or aliases all high sources.
- Do not repurpose the now-proven split bits as generic opcode/modifier bits.
- Restrict or replace high-register `get_sr` allocation until its real bank and
  publication mapping is understood.
- Treat G16 and G17 as one Apple9 ISA here; no tested ALU result requires a
  generation split.
