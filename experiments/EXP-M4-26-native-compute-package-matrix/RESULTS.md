# EXP-M4-26 results: native T8132 compute packaging matrix

Two independent fresh-process runs completed every workload with exact output,
immutable inputs, and 768 checked output-guard bytes per dispatch:

- `m4-20260829-typebits01`
- `m4-20260829-typebits02`

The later logic-transition extension was also repeated from fresh processes:

- `m4-20260829-logictrans01`
- `m4-20260829-logictrans02`

`raw/runs/m4-20260829-logictrans-repeat-analysis.json` confirms that every
audited package field is byte-identical between those two runs.

`analyze.py` verified that the archive header, sized shader block, constant
program, launch wrapper, decoded state record, first direct-CDM record, and
resource table are byte-identical between the two runs for every workload.
Other process mappings may be added, omitted, or contain process-local data;
those mappings are deliberately not treated as package fields.

## Stable interface fields

All nine workloads use the same native 0x340-byte archive header and direct-CDM
record.  The two-input/one-output workloads use one three-entry resource
interface.  `mix4` extends that interface to three inputs and one output without
changing the archive header, constant program, or direct-CDM form.

The three-buffer cases split into two launch/compiler profiles:

| Workload | Main operation | Archive block | launch `+0x5a` | state literals |
| --- | --- | ---: | ---: | --- |
| `add3` | float add | `0xc0` | `0x04` | none |
| `iadd3` | uint add | `0xc0` | `0x04` | none |
| `fmul3` | float multiply | `0xc0` | `0x04` | none |
| `fconst3` | float add plus `2.0f` | `0xc0` | `0x04` | none |
| `dag3` | multi-operation uint DAG | `0x100` | `0x00` | `0x00ff00ff` |
| `reuse3` | fanout/reuse uint DAG | `0x100` | `0x00` | `0x00ff00ff`, `0x55aa55aa` |

This rules out interpreting launch byte `+0x5a` as a float-mode bit.  It is an
instruction byte in the native launch program and is selected with a compiler
property that, for this matched interface, also separates the small and large
programs.  The evidence does not yet identify that property, so Mesa must not
derive the byte from source type or program size alone.

Native Metal materializes the large integer masks in the 0x40-byte state
record.  `fconst3` keeps `2.0f` out of that record.  This is a compiler choice,
not evidence that every Apple9 main requires state-backed constants: a Mesa
main which constructs a constant inline must be tested with a zero state record.

## Logic producer/consumer transitions

Five additional own-source kernels isolate terminal logic, logic consumed by
integer add, integer add consumed by logic, and a compiler-optimization
control.  All exact outputs and guards passed twice.

| Workload | Expression | Block | launch `+0x5a` | State literals |
| --- | --- | ---: | ---: | --- |
| `xor3` | `a ^ b` | `0xc0` | `0x04` | none |
| `xoradd3` | `(a ^ b) + a` | `0x100` | `0x00` | none |
| `andadd3` | `(a & b) + a` | `0x100` | `0x00` | none |
| `addxor3` | `(a + b) ^ a` | `0xc0` | `0x00` | none |
| `xorxor3` | `(a ^ b) ^ a` | `0xc0` | `0x10` | no state pointer |

`xorxor3` is a negative control: the native compiler simplifies it to `b`,
omits declared buffer A from the physical resource table, and selects the
ordinary two-buffer launch shape.  The analyzer checks that optimized
two-entry interface explicitly rather than pretending all declared Metal
arguments survive compilation.

The exact native `xoradd3` arithmetic body is:

```text
load A -> r0
load B -> r2
2b 05 2e 81 02 08 00 80 00 00    r2 = r2 ^ r0
9f 01 54 00 02 08 00 a8 17 05    r0 = r2 + r0
e7 00 54 ...                       implicit store from r0
```

The logic instruction destructively replaces dead B in `r2`; the final add
destructively replaces A in `r0`.  For `andadd3`, only the logic selector
changes (`2e/02 08` to `2f/00 00`).  By contrast, terminal `xor3` uses:

```text
0b 05 1e 01 02 08 00 80 00 00
```

The consumed XOR retains source 1 through the correlated transition
`bit31=1, bit20=0, bit21=1`, while bit 63 remains one.  This is direct native
counterevidence to the earlier generalization that retaining *either* logic
source always clears bit 63.  Source-0 retention and source-1 retention must be
modeled independently, together with destructive producer/consumer topology;
blindly copying only the following IADD's `0x54` envelope produced zero on
hardware.

These cases also reinforce that launch byte `+0x5a` is not a scalar resource
count, source type, literal-presence, or block-size field.  `addxor3` and
`xoradd3` have the same three-buffer interface and zero state literals but use
different wrapper values; Mesa must treat it as compiler-package metadata until
its semantic input is isolated.

## Other resource counts

| Workload | Buffers | Archive block | launch `+0x5a` |
| --- | ---: | ---: | ---: |
| `store1` | 1 | `0xc0` | `0x02` |
| `copy2` | 2 | `0xc0` | `0x10` |
| `mix4` | 4 | `0x100` | `0x00` |

The byte values across different launch shapes are not comparable as a common
field.  `copy2` also proves that native resource allocations may occupy fixed-USC
`+0x18000`; its launch does not use the one/three-buffer state-pointer encoding.
The analyzer therefore decodes the launch pointer before naming a state record
and resolves resource addresses inside larger captured mappings.

## Two-buffer scalar-map packaging

Three fresh-process captures, two in forward order and one in reverse order,
completed all 18 workloads with exact outputs, immutable inputs, and intact
guards:

- `m4-20260830-scalarmap01`
- `m4-20260830-scalarmap02`
- `m4-20260830-scalarmap-reverse`

For `copy2`, `uadd7`, `xorimm`, `andimm`, and `fanout`, the complete audited
package is stable across all three runs and independent of case order.  The
five cases have an identical `0x340` archive header, `0xc0` archive-block
allocation, constant program, `0x100` launch snapshot with byte `+0x5a = 0x10`,
absent dynamic state, direct-CDM record, and normalized two-pointer resource
table.  Only the authored bytes within the archive block differ.

| Workload | Expression | Main bytes | State |
| --- | --- | ---: | --- |
| `copy2` | `out = a` | 36 | absent |
| `uadd7` | `out = a + 7` | 46 | absent |
| `xorimm` | `out = a ^ 7` | 46 | absent |
| `andimm` | `out = a & 0xff` | 46 | absent |
| `fanout` | `out = (a + 7) ^ (a & 0xff)` | 60 | absent |

Each case produced 64 exact values per run and retained all 768 output-guard
bytes.  The native fanout main contains exactly one device load followed by
multiple consumers.  Its load byte 3 changes from `0x00` in the single-use
cases to `0x04`, providing concrete evidence that native producer/liveness
metadata changes when the loaded value is reused.  That bit change is not a
package-interface change.

The forward/reverse comparison reports some differences in auxiliary
fixed-USC mappings for non-scalar cases.  No scalar-map case contributes to
them, no audited package field differs, and every result remains exact.  Those
unreferenced precommit bytes are therefore recorded as allocator/runtime
variation rather than promoted into the compute package.

## Multiple loads from one resource

Two fresh-process orderings of each focused matrix completed with exact
results, immutable 4-KiB inputs, and 3,840 checked output-guard bytes:

- `m4-20260830-multiload01` and `m4-20260830-multiload-reverse`
- `m4-20260830-loadscaling01` and `m4-20260830-loadscaling-reverse`
- `m4-20260830-addressing01` and `m4-20260830-addressing-reverse`

Every audited package field and every authored main is byte-identical between
the forward and reverse runs.  The analyzer now extracts the main, verifies its
complete SHA-256, and records every device-load instruction's raw bytes,
offset, destination, index, framing, and raw producer/cache token.  Token
serialization is understood; some producer semantics remain unresolved.

| Workload | Loads | Main bytes | Block | Dynamic state |
| --- | ---: | ---: | ---: | --- |
| `copy2` | 1 | 36 | `0xc0` | absent |
| `load2_reduce` | 2 | 70 | `0x100` | absent |
| `load2_reuse` | 2 | 84 | `0x100` | absent |
| `load2_far` | 2 | 70 | `0x100` | one offset, `0x240` |
| `load3_reduce` | 3 | 104 | `0x100` | absent |
| `load4_reduce` | 4 | 132 | `0x140` | absent |
| `load6_reduce` | 6 | 200 | `0x180` | `0x100`, `0x140` |
| `load8_reduce` | 8 | 268 | `0x1c0` | `0x100` through `0x1c0` |
| `load9_reduce` | 9 | 302 | `0x1c0` | `0x100` through `0x200` |
| `load10_reduce` | 10 | 330 | `0x200` | `0x100` through `0x240` |

This separates three independent transitions:

1. `load2_reduce`, `load3_reduce`, and `load4_reduce` use one identical
   stateless `0x88` launch program.  Relative to the one-load wrapper, its only
   authored delta is launch `+0x2e: 0x04 -> 0x00`.
2. The paired offset experiment keeps `+0xff` inline and stateless, then moves
   `+0x100` into state uniform `u4`.  `load2_off256` uses the same authored main
   and launch profile as `load2_far`, with the state literal changed from
   `0x240` to `0x100`.  This establishes native compiler/package policy for
   these cases; it is not evidence of a hardware IADD limit.
3. `load9_reduce` retains the low-tier constant program and direct-CDM record
   while selecting its own launch.  Only `load10_reduce` changes the constant
   program and direct-CDM byte 2 from `0x08` to `0x88` in this family.  The
   transition is therefore between nine and ten loads for these native
   programs, but its underlying pressure/occupancy input remains unnamed.

## Addressing and the nine-load boundary

The addressing matrix ran in both fresh-process orders.  All 16 case
executions produced exact output, retained immutable 4-KiB inputs, and
preserved all 3,840 trailing output-guard bytes per case.  Every audited
package field was byte-identical across the two orderings; differences in
unreferenced auxiliary precommit BOs did not overlap any package field.  The
two `source.sha256` manifests and two build-metadata records are independently
present and byte-identical.

The analyzer now gates these additional complete main tuples:

| Workload | Main bytes | Loads | SHA-256 |
| --- | ---: | ---: | --- |
| `copy2_off1` | 46 | 1 | `5162b1405d2201e86d2867f6585951fe4f411d3da95ceb67b95951e494bc00a3` |
| `copy2_affine` | 56 | 1 | `4fa4f3517af232f62baa90c5e4a5d8e7bf22ad443aef27787c8c4ed991402945` |
| `load2_off255` | 70 | 2 | `5806ad8b902c4b7e08d6549ec3cc9a82254a83cf3a157dc89a6f98a5cf72cfbd` |
| `load2_off256` | 70 | 2 | `2082239febfedae1f9be99bfde4934938c96edfb829bef844be0255093619c9d` |
| `load9_reduce` | 302 | 9 | `af18c8b97c151e18f206bd2be9c201a99fb910cca17fa82ac047d8b5c1db5da9` |

`copy2_off1` and `copy2_affine` retain the ordinary stateless copy wrapper:
their archive header, constant program, complete launch, absent state, direct
CDM, and normalized two-pointer resource table match `copy2`; only their sized
block and authored main differ.  `load2_off255` is likewise inline and
stateless.  `load2_off256` instead selects state and places `0x100` in `u4`;
its 70-byte main is byte-identical to `load2_far`, whose corresponding state
literal is `0x240`.  The load-scaling analyzer gates the far main, launch, and
complete state record, while the addressing analyzer gates the same main and
launch with the `0x100` state record.  The `0xff/0x100` split is therefore
recorded only as the native compiler/package choice observed here, not as an
Apple9 instruction limit.

`load9_reduce` shares the low-tier constant program and CDM record used by
copy/load8 but has a distinct launch from both load8 and load10.  Load10 alone
uses the high-tier constant/CDM pair in this addressing family.  This isolates
the launch transition from the later constant/CDM transition without assigning
either an unsupported architectural field name.

The native device-load group has a repeatable structure.  For two or more
loads, none carries the old `FIRST` bit.  Every non-final load has byte 2
`0x54`; the final load has `0x44`.  The first load consumes the real global
invocation-index SSA fixed to r1 and encodes that source directly as `0x01`;
subsequent native indices are encoded as `0x80 | physical_GPR`.  Clearing the
high bit on the matched r2 consumer was exact, whereas changing the r1 source
from `0x01` to `0x81` corrupted output.  The high bit is therefore
producer/schedule-sensitive, not a universal computed-index flag.  Most
importantly, `byte3 >> 1` is the load's actual destination GPR.  Native
reductions consume those GPRs directly and produce the exact expected output.

The two raw producer/cache bytes are independent of that destination.  They
advance in pairs across a long group:

```text
loads 0-1  51:01
loads 2-3  11:00
loads 4-5  51:00
loads 6-7  91:00
loads 8-9  d1:00
```

Mesa can now serialize all five raw classes.  The last two remain semantically
unnamed and map to unresolved producer provenance rather than being rejected
as unrepresentable.  Direct use requires a compatible producer/consumer tuple,
not necessarily the unique native tuple: coherently recoding load4's final
pair to `51:01` while selecting route 6 and clearing consumer bit 12 preserved
exact output.  Mesa's independently executed load-plus-zero-IADD remains the
conservative normalization boundary for a general ALU DAG.

The reverse `load8_reduce` dump omitted some auxiliary BO images that the
forward dumper retained.  Its required mappings, complete main and package,
exact result, and guards are identical.  The analyzer reports this as BO-set
variation without treating it as a package mismatch.

## Bring-up consequence

The stable boundary is an interface-specific package wrapper plus a separately
compiled main.  The two-resource wrapper is a stateless integer scalar-map ABI,
not a copy-only ABI: bounded arithmetic, logic, and one-load fanout programs can
reuse it without synthesizing a state pointer.  Constants which Mesa cannot
encode compactly must be constructed inside the main until a separately
captured two-buffer state-bearing interface exists.  The exact native copy main
remains a useful specialization and byte oracle, but it no longer defines the
semantic limit of the wrapper.

Mesa's corresponding exact-output T8132 regression subsequently executed twelve
independently compiled scalar-map programs in one persistent Gallium context,
with two launches and 256 invocations per program.  All 24 dispatches matched
both complete guarded `0x5000`-byte BOs and reached queue/channel counters
12/12/12.  In addition to the native expressions above, the regression covers the
compact-immediate `0x7f`/`0x80` boundary and
`(x ^ 0x55aa55aa) + x`; the latter proves that the normalized device-load value
can be reused and that an integer-logic result can feed IADD.  Dedicated
compositional builders execute `a[i] + a[i+64]` and
`(a[i] + a[i+64]) ^ (a[i] - a[i+64])`.  Each checks 320 immutable input words,
256 exact output words, and the complete surrounding allocations.  An
intentionally undersized input binding is rejected without advancing dispatch,
launch, or resource publication state.  The package selector is shared as a
stateless multi-load ABI, while the compiler profile carries the per-main
access tail.  Compositional `load3_reduce` and `load4_reduce` builders add the
captured `(A+B)^C` and `(A+B)^(C+D)` mains, with `0x200` and `0x300` input tails
respectively.  The latter's 132-byte main also verifies the larger `0x140`
executable-block allocation.  Each of the four generated mains is independently
compared byte for byte with its complete native oracle and passes the host
compiler tests.  This validates compositional reproduction of the four
captured mains; it does not yet claim arbitrary load-group scheduling or token
allocation.  After conversion of all four mains, a cold chainload followed by
the full 12-formula, two-dispatch suite produced exact complete `0x5000`-byte
BOs for all 24 dispatches.  It completed 12 publications with queue, channel,
and stamp counters at 12/12/12.

## Executed device-load ablations

Mesa's guarded scalar-map fixture can apply strictly parsed byte patches to a
native-byte-identical selected main before archive insertion.  Each probe below
began from a cold target, retired normally, and compared the complete input and
output BOs; alternate semantic oracles were used where the mutation
intentionally changed the selected plane.  Offsets are relative to the authored
main.

| Main/probe | Patch | Result |
| --- | --- | --- |
| load2 first index, same register with high bit | `+0x13: 01 -> 81` | retired with deterministic wrong data |
| load2 computed index high bit removed | `+0x21: 82 -> 02` | exact baseline |
| load2 first index redirected to `r2` | `+0x13: 01 -> 02` | exact `B+B` for all 256 lanes |
| load2 add `FIRST` | `+0x0f: 00 -> 10` | exact baseline |
| load2 clear first `HAS_NEXT` | `+0x10: 54 -> 44` | exact baseline |
| load2 second raw token | `+0x24:25: 51:01 -> 11:00` | exact baseline |
| load2 IADD byte 4 | `+0x2e: 02 -> 03` | exact baseline |
| load3 final raw token | `+0x3c:3d: 11:00 -> 51:01` | exact baseline across two dispatches |
| load4 compact XOR duplicate source | `+0x6f: 05 -> 01` | exact zero for every lane |
| load4 compact XOR swap sources | `+0x6f: 05 -> 01`, `+0x71: 01 -> 05` | exact baseline across two dispatches |
| load4 index cross-selection | `+0x35: 84 -> 82` | neither baseline nor the naive `(A+C)^(C+D)` oracle |
| load4 second-pair IADD bit 12 clear | `+0x65: 11 -> 01` | retired with corrupted output |
| load4 second-pair IADD route 6 | `+0x66: 54 -> 56` | exact baseline |
| load4 coherent final-pair recode | `+0x46:47, +0x54:55: 11:00 -> 51:01`; `+0x65: 11 -> 01`; `+0x66: 54 -> 56` | exact baseline |

These results sharpen the earlier model:

- The low seven index bits select an architectural GPR: redirecting load2's
  first load from the real r1 SSA source to the immediately authored `r2`
  address produced exactly `B`.
- Index byte bit 7 is not a universal computed-index toggle.  It was
  output-inert on the native `r2` consumer, but setting it on the r1 SSA path
  broke output.  Reusing load4's authored `r2` index earlier than its
  native consumer also broke the naive alternate oracle.  Index values retain
  producer/lifetime coupling in addition to their register number.
- The isolated `FIRST`, `HAS_NEXT`, load2/load3 raw-token, and load2 IADD-mode
  changes were output-inert in their short-lived reductions.  Load4's bit 12
  was not: clearing it alone corrupted output, while route 6 alone was exact.
  Recoding both final load tokens and the consumer together was exact, showing
  that these fields form compatible scheduling tuples rather than one unique
  architectural value identity.
- The compact four-byte XOR really consumes the two preceding pair sums and
  publishes its destination to the implicit store.  Duplicating one operand
  produced exact zero; swapping operands preserved exact output.

The conservative compiler rule therefore remains sound: device-load indices
and results are real SSA values, but arbitrary scheduling must still preserve
their constrained physical placement, producer lifetime, and compatible
consumer encoding.  Raw token identity must remain separate from semantic
producer provenance in that model.

Reproduce the host audit with:

```sh
python3 analyze.py raw/runs/m4-20260829-typebits01 \
  --repeat raw/runs/m4-20260829-typebits02

python3 analyze.py raw/runs/m4-20260830-scalarmap01 \
  --repeat raw/runs/m4-20260830-scalarmap-reverse

python3 analyze.py raw/runs/m4-20260830-multiload01 \
  --case-set multiload \
  --repeat raw/runs/m4-20260830-multiload-reverse

python3 analyze.py raw/runs/m4-20260830-loadscaling01 \
  --case-set loadscaling \
  --repeat raw/runs/m4-20260830-loadscaling-reverse

python3 analyze.py raw/runs/m4-20260830-addressing01 \
  --case-set addressing \
  --repeat raw/runs/m4-20260830-addressing-reverse
```
