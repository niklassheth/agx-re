# EXP-M4-32 results

## Result

The public corpus produces strong new evidence that instruction bits 45–47 are
a three-bit selector for transient publication/return state, not a small enum
limited to the values observed in EXP-M4-31 and not a producer-class tag.

In fully descriptor-decoded programs, ordinary binary `falu2` add/multiply
forms use every value from 0 through 6:

| Candidate route | Qualified instruction instances |
|---:|---:|
| 0 | 1,790 |
| 1 | 87 |
| 2 | 26 |
| 3 | 18 |
| 4 | 11 |
| 5 | 11 |
| 6 | 318 |

Values 3, 4, and 5 were absent from the controlled EXP-M4-31 matrix.  They are
not decoder-prefix artifacts: all 40 instances above occur in programs whose
entire stage main has known instruction lengths and matched descriptors.  They
span PyTorch activation, attention and reduction kernels plus MLX GEMV and SDPA
kernels.  Route 7 appears natively in a six-byte `opsel=6` FMA continuation
form, described below, but not in the fully decoded basic binary add/multiply
subset.  It must not be counted as a binary-`falu2` witness merely because the
permissive six-byte descriptor currently gives both forms the same mnemonic.

`falu2i` is less diverse in the fully decoded subset: routes 0, 1, 2, and 6
occur.  Direct `ilogic` XOR has ten fully decoded instances, all route 0.  A
10-byte logic shape previously treated as downstream XOR in EXP-M4-31 is also
emitted for equality operations in the broad corpus, so its global semantic
name is now explicitly left unresolved.

## Seven-load GEMV witness

The clearest witness is MLX
`gemv_float32_bm1_bn8_sm1_sn32_tm1_tn4_nc0_axpby0`.  Its fully decoded main has
seven consecutive `device_load` instructions at offsets `0x466..0x4ba`, followed
by this accumulation sequence:

| Offset | Instruction | Source registers | Bits 45–47 |
|---:|---|---|---:|
| `0x4c8` | `falu2 add` | 16, 0 | 6 |
| `0x4ce` | `falu2 add` | 0, 10 | 1 |
| `0x4d4` | `falu2 add` | 0, 8 | 2 |
| `0x4da` | `falu2 add` | 0, 7 | 3 |
| `0x4e0` | `falu2 add` | 0, 5 | 4 |
| `0x4e6` | compact `falu_acc` | compact operands | no field |
| `0x4ea` | `falu2 add` | 0, 1 | 5 |

The explicit selectors therefore run through 1–6 in one compiler-generated
consumer chain.  The compact instruction between routes 4 and 5 has its own
`cache=1` encoding and no bits 45–47; assigning it route 0 would be plausible,
but this experiment does not make that inference.

This sequence is difficult to explain as unrelated source modifiers.  It is the
shape expected from a finite set of outstanding return/publication slots: issue
several loads, then identify which transient result a later ALU operand consumes.

## Same instruction, different schedule

After clearing only bits 45–47, the byte-identical `falu2` encoding
`590d3d0b0000` occurs in two independently designed SDPA implementations:

| Corpus/function | Native bytes | Route | Local context |
|---|---|---:|---|
| PyTorch `sdpa_vector_2pass_2_float_96` | `590d3d0b0060` | 3 | interleaved `simd_reduce` and `falu2` |
| MLX `sdpa_vector_float_64_64` | `590d3d0b00c0` | 6 | interleaved `simd_reduce` and `falu2` |

The opcode, register operands, operation, and non-route modifiers are identical.
Only the surrounding native schedule and candidate route differ.  This directly
contradicts any rule that assigns the field from opcode or static source type.

## Additional route-shaped instruction families

`analyze_additional_route_fields.py` extends the census beyond the original
binary `falu2`, `falu2i`, and direct-XOR scope.  It qualifies semantic opcode
forms inside permissive descriptors before counting them.  The table below is
the strongest subset: instruction instances in stage mains whose complete byte
stream has known lengths and matched semantic descriptors.

| Family | Candidate field | 0 | 1 | 2 | 3 | 4 | 5 | 6 | Same non-field bytes at multiple values |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `falu3` FMA | bits 61–63 | 1,623 | 68 | 39 | 38 | 3 | 3 | 138 | 4 encodings |
| wide `isel10` | bits 61–63 | 880 | 0 | 0 | 0 | 0 | 0 | 49 | 13 encodings |
| extended binary FALU | bits 45–47 | 312 | 14 | 2 | 0 | 2 | 0 | 0 | 0 encodings |
| native-half binary ALU | bits 45–47 | 2 | 2 | 0 | 0 | 0 | 0 | 38 | 0 encodings |
| native-half extended ALU | bits 45–47 | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 encodings |
| float unary/modifier | bits 45–47 | 141 | 0 | 0 | 0 | 0 | 0 | 0 | 0 encodings |
| long logic/setup | bits 45–47 | 841 | 16 | 1 | 0 | 0 | 0 | 0 | 0 encodings |

The broad usable-prefix census sees additional values in several rows, but they
are not needed for the conclusions here.  The complete-program counts avoid
promoting values that could depend on an incompletely described surrounding
stream.

### FMA is the strongest cross-instruction match

PyTorch `naive_bmm_float` contains six consecutive `device_load` instructions
at offsets `0x35c` through `0x3a2`.  Its subsequent `falu3` instructions use:

| Offset | Native bytes | Bits 61–63 |
|---:|---|---:|
| `0x3b0` | `59397e2b810402c0` | 6 |
| `0x3b8` | `69357e2d812a0220` | 1 |
| `0x3d0` | `59337e3181040260` | 3 |
| `0x3e2` | `09297e21812a0280` | 4 |
| `0x3f0` | `c91b3e25810402a0` | 5 |
| `0x3f8` | `29171e2781180240` | 2 |

Thus one fully decoded native main uses every nonzero selector 1–6 after filling
the machine with outstanding loads.  PyTorch `matmul_half` and `matmul_bfloat`
independently use the same complete set.  This is the FMA analogue of the
seven-load binary-FALU GEMV witness.

The field is also schedule-polymorphic after holding the rest of the
instruction fixed.  For example, normalized FMA bytes
`59143e14810a0a00` occur as route 1 (`...20`) in
`gemv_nt_half_8_1_none_xs_strided` and route 6 (`...c0`) in
`gemv_nt_half_4_1_ab_xs`.  Four such normalized FMA encodings are polymorphic
inside fully decoded programs.  This strongly supports a shared transient-slot
selector across binary and ternary float consumers, with the FMA field moved to
bits 61–63 by its longer operand layout.

### Select and half-precision evidence

Wide `isel10` remains consistent with the controlled route experiments.  The
public complete subset happens to use only routes 0 and 6, but 13 otherwise
identical encodings switch between those values under different schedules.  A
particularly clean pair is normalized encoding
`02880780860007028204`: route 0 in MLX `g2_Maximumint64`, versus route 6
immediately after three device loads in MLX `v_Selectint64`.  The broader usable
prefix set also contains routes 1, 2, 3, and 4; the controlled experiments,
rather than those partial programs, remain the primary evidence for routes 1
and 2.

Native-half binary ALU is suggestive but not yet closed.  A route-6 multiply in
`mul_dense_scalar_lhs_half_half` immediately consumes a device load, while a
route-0 multiply in `gn1_FromFP8uint8float16` consumes an ordinary materialized
value.  Route 1 also occurs in complete programs.  This means the existing
description of high bits `0xc0` as an always-required operand-valid base is too
broad: native Metal emits valid semantic half add/multiply forms with high bits
0 and 1 as well.  A controlled half-ALU schedule cross is needed before naming
the field a route outright.

Extended binary float forms are compatible with the shared model (routes 0, 1,
2, and 4 in complete programs), but no completely decoded corpus pair holds all
other instruction bits fixed while changing only this field.  Unary float does
not show the distribution: every complete instance has zero in bits 45–47.
The long logic/setup family has some nonzero values, but its `modB` byte covers
multiple unresolved operations, so these counts are not semantic route evidence.

The machine-readable counts, exact contexts, normalized-encoding witnesses, and
richest complete programs are in `ADDITIONAL_ROUTE_CENSUS.json`.

### Route 7 audit

No semantically qualified, fully decoded native program in this corpus uses
route 7 in basic `falu2`, `falu2i`, `falu3`, `isel10`, extended binary FALU,
or native-half ALU.  The raw census also found 75 route-7-looking six-byte
records in three MLX kernels:
`affine_qvm_float_gs_{32,64,128}_b_4_batch_0`.  The original conclusion that
these were probably false instruction boundaries was too strong.

The streams really do expose decoder bugs, but they are neighboring bugs:

- A purported ten-byte `n3_addr_prep`, for example
  `43 80 27 8f 10 02 00 00 00 00`, has texture `op_variant=0x8f`, while the
  native texture-only form admits `0xbf`, `0x36`, or `0x22`.  It splits cleanly
  into a four-byte low-nibble-3 move and a six-byte record.
- Records such as
  `c9 f7 e3 f4 a7 07 54 7e 03 10 a4 20` are not twelve-byte extended FALUs:
  their first word has no valid long-FALU op-select and the last eight bytes
  are an independently recognized `cvt_i2f`.
- Eight-byte records such as `09 7d ca f3 a9 7b 8a f3` are two adjacent
  four-byte compact low-nibble-9 words.

The current length oracle uses bytes belonging to the following compact
instruction as extension selectors, so it over-consumes 84 records in each
qvm main: 31 low-nibble-3 pairs, 44 compact-word-plus-convert pairs, and nine
pairs of compact float words.  Every audited correction preserves the same
total byte count and therefore does not move the later six-byte boundaries.

After making that structural distinction, every main still contains the same
ordered sequence of 25 six-byte `opsel=6` records.  There are seven byte forms,
all with bits 45--47 equal to 7.  Seventeen of the 25 are immediately followed
by a recognized `cvt_i2f`; the remaining successors are other repeated FMA or
move forms.  The `gs_64` and `gs_128` bodies use the same offsets, while the
`gs_32` body is shifted earlier by 32 bytes.  The concatenated sequence of the
25 records is byte-identical in all three mains.  This is a repeated native
compiler pattern, not an accidental scan landing.

The source explains the form.  The four-bit `qouter` path keeps 32 float
accumulators live and unrolls nested operations of the shape
`result += x * (scale * nibble + bias)`.  That naturally produces compact /
continuation FMAs under unusually high register and return-state pressure.  An
own-source reduction in `qvm_route7_minimal.metal` preserves only that nested
FMA and varies the live unrolled result count.  Native Metal emits the same
six-byte `opsel=6` family with bits 45--47 equal to 4 in `q4_n8`, 5 in the fully
decoded `q4_n16`, and 6 in `q4_n24`/`q4_n28` before those larger programs reach
an unrelated decoder gap.  The full MLX schedule selecting 7 is therefore
consistent with the same allocation field progressing under greater pressure.

This promotes one narrow statement: native Metal emits value 7 in bits 45--47
for the six-byte FMA-continuation form.  It does not yet prove that the field
has identical operand ownership in binary add/multiply and FMA, nor does it
provide a hardware mutation result for these exact qvm instructions.  The
machine-readable split witnesses, exact offsets, forms, and own-source archive
hashes are in `QVM_ROUTE7_AUDIT.json`.

Six further route-7-looking values occur in the unresolved long-logic/setup
`modB` field, only in incomplete programs; that byte is still not established
as a route field.

Route 7 is nevertheless not universally illegal in hardware.  Earlier
controlled ISELECT mutations changed a native route-2 ALU case to route 7 and
remained exact in 74/74 executions.  Smaller producer panels also accepted
route 7 for texture, threadgroup, atomic, subgroup, and predicate cases, while
the device-load case produced wrong output.  Those were patched instructions,
not Metal output, and do not independently establish the FMA field's operand
ownership.  Combined with the native qvm records, however, they no longer
support treating 7 as merely a reserved or illegal value.  The stronger
working hypothesis is now that 7 is a real compiler-allocatable state reached
by the high-pressure FMA schedule.  Its exact lifetime and source-slot meaning
remain open.

## Updated hypothesis

The best current model is:

- Bits 45–47 select a transient return/publication slot for the relevant source
  operand of the long instruction form.
- The encoded GPR/source descriptor and the route selector are distinct pieces
  of the operand reference.
- Compact ALU forms have an implicit cache/route relationship and therefore do
  not expose the same three-bit field.
- Producer kind affects which transient mechanism is used, but does not name the
  route.  The same producer family can receive different selectors under a
  different outstanding-result schedule.
- A preceding read can release or recycle a transient slot.  That reconciles the
  EXP-M4-31 “recently read return slot” effect with the new high-occupancy data:
  recent use changes allocator state; it is not itself the route definition.

This remains a model, not a completed semantic map.  We still need a controlled
own-source version of the seven-load chain, then coordinated load-issue and
consumer-order changes with exact output oracles.  Those tests should determine
whether selector 0 is the compact implicit route, whether slots are freed on
last use, and which operand owns the field when two transient sources are used.

## Corpus and decoder coverage

- 111 public Metal translation units.
- 35,163 accepted Apple-M4 compute pipelines.
- 30,560 unique `_agc.main` programs.
- No archive extraction failures.
- 4,048 programs have complete known instruction lengths.
- 3,620 programs have complete lengths and semantic descriptors.
- 32,365 descriptor-qualified candidate-route instruction instances in all
  usable prefixes.
- 2,409 `falu2` and 628 `falu2i` instances in the strongest fully decoded
  subset.
- The compressed full assembly ledger contains 1,401,141 length-qualified
  records, of which 1,398,927 have semantic descriptors.  Its exact SHA-256 and
  size are recorded in `ASSEMBLY_INDEX.json`.

The low whole-program completion fraction is a decoder-coverage limitation, not
a Metal failure.  Prefix evidence ends at the first unknown instruction length;
no resynchronization or byte-pattern search is used.  The primary route-3/4/5
claims above rely only on the fully decoded subset.

## Native refusals

Four exported specializations did not produce archives:

- PyTorch `svd_jacobi_float` and `svd_jacobi_float2`: the Metal compiler service
  connection was interrupted after retries.
- Two MLX float32 Steel attention variants: declared threadgroup memory was
  40,448 and 53,760 bytes, above the device's 32,768-byte limit.

All other enumerated kernels produced archives.  No target fault or hang
occurred.  These shaders were compiled and pipeline-validated but not executed;
semantic hardware claims still come from the controlled experiments.
