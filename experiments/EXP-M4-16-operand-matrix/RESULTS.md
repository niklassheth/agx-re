# EXP-M4-16 results — Apple9 operand matrix

## Allocator-facing matrix

| Encoding form | Length | Destination | Sources | Status |
|---|---:|---:|---:|---|
| `mov_imm` compact | 2 B | r0–r15 | immediate | allocator-safe |
| `get_sr` | 4 B | r0–r95 | special register | allocator-safe |
| `falu2` compact | 6 B | r0–r15 | GPR r0–r63 | allocator-safe within hard limits |
| float compact accumulate/move | 4 B | r0–r15 | compact descriptor | incomplete |
| float modifier/saturate | 8/10 B | r0–r15 | modifier-coupled | incomplete |
| GPR FMA | 8 B | r0–r95 | three GPRs r0–r95 | allocator-safe for 32-bit GPRs |
| integer add/sub register | 10 B | r0–r95 | two GPRs r0–r95 | allocator-safe for 32-bit GPRs |
| integer MAD/mul register | 12 B | r0–r95 | three GPRs r0–r95 | allocator-safe for 32-bit GPRs |
| min/max compact | 6 B | r0–r15 | two GPRs r0–r63 | allocator-safe within hard limits |
| GPR compare/select wide | 10 B | r0–r15 | four GPRs r0–r95 | allocator-safe for 32-bit GPRs |
| logic compact | 4 B | r32–r63 | two GPRs r0–r63 | allocator-safe within hard limits |
| logic extended | 10 B | r0–r95 | two GPRs r0–r95 | allocator-safe except all-three-high tuple |
| variable shift | 8–12 B | form-dependent | unresolved | incomplete |
| device load | 14 B | r0–r95 | r0–r95 index | allocator-safe for established widths |
| device store | 14 B | producer-coupled | r0–r95 index | scheduling constraint unresolved |

The physical model is common to G16 and G17: 96 32-bit GPRs, 192
independently allocatable 16-bit halves, hardware register interlocks, no
G13-style software wait insertion, and a pressure-selected occupancy tier.
Spilling remains disabled until the Dynamic-Caching scratch ABI is known.

## Capture method

All compiler captures came from caller-owned MSL compiled with the public
Metal API on the target M4. macOS was launched only through the repository's
hypervisor `run_guest.py` route. No proprietary executable was disassembled or
decompiled. The 63/64/65 pressure variants use a fixed stride of 96, removing
the earlier power-of-two-addressing confound.

## Exact integer fields

The register-register forms expose independent contiguous seven-bit GPRs:

- IADD: destination `[25:32]`, source A `[42:49]`, source B `[51:58]`.
- IMAD: the same three fields plus source C `[60:67]`.

T8132 probes tested every IMAD role independently at r64 and r95. All eight
boundary probes produced exact `3*4+5`, queue `1/1/1`, firmware stamp `0x100`,
and ordered nonzero timestamps.

## Compact float and min/max limits

The six-byte float and min/max source descriptors reach r0–r63. Descriptor
bit 7 is cache/liveness state, not GPR bit 6. Their destination is a hard
r0–r15 nibble. Min/max probes validated destination r15 and both sources at
r63. The earlier guessed high-register min/max splice is retained only as a
negative control; high GPRs require a different encoding.

## Exact compact and extended logic forms

The compiler uses two allocator-relevant encodings for ordinary two-input
boolean operations:

| Form | Destination | Source A | Source B |
|---|---|---|---|
| 4-byte compact | `r32 | [4:8] | ([22] << 4)` | `[9:15]` | `[25:31]` |
| 10-byte extended | `[4:8] + [22:24] + [44]` | `[9:15] + [40]` | `[25:31] + [42]` |

The compact form therefore has an unusual hard destination bank of r32–r63,
not the r0–r15 bank used by compact float/minmax instructions. Its sources are
six-bit r0–r63 GPRs. The extended form reaches every physical role through
r95; its extension bits are specific to the logic family and are not the FMA
extension-bit positions.

The fixed-stride N=63/64/65 AND and XOR streams contain the same physical
register graph for each N. Across one operation family per N this isolates 57
compact and 135 extended operations. T8132 then validated compact destination
r32/r63 and each source at r63. For the extended direct form, destination,
source A, and source B each work independently at r64 and r95. Both high
sources work together, and a high destination works with either one high
source. The tuple `(dst=r95, srcA=r64, srcB=r65)` retires without producing a
store, so the first allocator must cap this form at two simultaneous r64–r95
operands. That is a cross-operand constraint, not a reduction in the individual
field ranges.

The ordinary compiler SSA envelope and the directly-store-consumed LUT
envelope have different fixed family/control bits but the same physical
register layout. The ISA database models them separately to prevent those
control bits from being mistaken for register extensions.

Representative logs:

- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_logic_and-compact-dst-r63_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_logic_corrected_and-dst-r95_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_logic_combo_and-both-sources-high_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_logic_combo_and-dst-r95-src-a-r64_20260825.log`
- negative: `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_logic_corrected_and-all-high_20260825.log`

## Exact FMA GPR form

The eight-byte GPR FMA scatters the seventh register bits:

| Role | Low bits | Middle/high bits |
|---|---|---|
| destination | instruction `[4:8]` | `[22:24]`, `[60]` |
| source A | `[9:15]` | `[56]` |
| source B | `[25:31]` | `[58]` |
| source C | `[41:47]` | `[38]` |

The fixed-stride rings prove `B[i] == A[i+1]` and `C[i] == A[i+2]` for every
operation across N=63/64/65. A second kernel consumes each FMA destination
through the independently decoded integer add, fixing all destination bits.
Finally, eight T8132 programs exercise destination, A, B, and C independently
at r64 and r95. Every program produced exact `2.0f` output with normal
retirement. Modifier/cache/source-file bits remain distinct from these physical
register bits; the current allocator-safe claim is for the proven 32-bit GPR
form, not every 8/10/12-byte overload.

Representative logs:

- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_fma_dst_r64_corrected_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_fma-dst-r95_corrected_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_fma-src-c-r95_corrected_20260825.log`

## Exact wide GPR select form

The explicit-false ten-byte form has an asymmetric register contract:

- destination `[4:8]`, hard r0–r15;
- cmpA low `[9:15]`, high `[56]`;
- cmpB low `[25:31]`, high `[58]`;
- true low `[41:47]`, high `[38]`;
- false low `[73:79]`, high `[70]`.

Fixed-stride N=63/64/65 rings verify all source identities. N=64 contains one
eight-byte folded-false sibling; the other 191 operations are the ten-byte
form. Hardware tests validate the low baseline and destination r15, plus each
of the four sources independently at r64 and r95. The deliberate destination
r64 splice retires but performs no store, proving bit60 is select control state
rather than a destination extension.

Representative logs:

- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_select-dst-r15_corrected_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_select-cmp-a-r95_corrected_20260825.log`
- `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_select-false-r95_corrected_20260825.log`
- negative: `/home/nsheth/Projects/asahi/logs/agx_operand_matrix_select-dst-r64_corrected_20260825.log`

## Remaining operand-matrix work

1. Compact accumulate/move destination/source fields.
2. Extended min/max and variable-shift forms for high GPRs.
3. The alternate logic encoding/control requirement for three simultaneous
   high-register operands.
4. GPR versus uniform/immediate source-class alternatives for each ALU family.
5. Complete 16-bit-half and 64-bit pair constraints outside proven memory ops.
6. Cache/liveness/modifier bits and compact-versus-extended cost selection.
7. Narrow/folded compare-select forms and predicate-producing compare forms.

The current Mesa machine table exposes only hardware-proven allocatable forms;
unresolved forms remain explicitly unavailable rather than guessing.
