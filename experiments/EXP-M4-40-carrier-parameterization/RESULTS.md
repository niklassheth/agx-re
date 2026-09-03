# EXP-M4-40: compute carrier parameterization

## Scope and clean-room boundary

This experiment varies public Metal dispatch parameters in own-source compute
programs and compares their caller-owned package objects. Metal-generated
launch programs and archive code are treated as opaque byte strings. They are
not disassembled or decoded.

The immediate question is whether indirect dispatch, threadgroup-memory size,
or register-pressure occupancy require different opaque launch-program
families in Mesa's temporary Apple9 carrier model.

## Indirect dispatch does not select another launch program

Existing direct/indirect captures establish one normalized geometry contract:

- direct dispatch publishes total threads in hidden tuple q0 and `{1,1,1}` in
  q1;
- indirect dispatch publishes raw group counts in q0 and local-size scale in
  q1;
- the launch-visible total is component-wise `q0 * q1`;
- the indirect CDM record points at q0.

The archive and opaque launch executable remain unchanged. A source-built
carrier ablation changed a 64-thread direct dispatch to indirect groups
`{4,1,1}` with local size `{16,1,1}`. T8132 produced the complete exact output
oracle and retired normally:

`/home/nsheth/Projects/asahi/logs/apple9_carrier8_indirect_4x1x1_local16_20260902.log`

The existing Apple9 Mesa path currently rejects indirect dispatch before
publication. Merely removing that rejection would expose a latent builder bug:
it later reads `grid.count[]` from the indirect-grid union and always authors
the direct hidden tuples. The mode-specific construction needs to be:

- direct: resource q0 points to the total-thread tuple and q1 to `{1,1,1}`;
- indirect: resource q0 is the caller's raw group-count address and q1 points
  to the API local-size tuple;
- indirect CDM: the split pointer at `+0x10` names that same q0 record.

There is no CPU-known total-thread tuple in the indirect case. The unchanged
launch code derives it at execution time as `q0 * q1`.

## Threadgroup memory is one patchable allocation word

The own-source matrix dispatches the same dynamic-shared-memory pipeline at
128, 256, 512, and 1024 bytes, followed by an independently compiled static
128-byte control. Every case compares the entire 4-KiB output against a CPU
oracle, checks the unwritten guard, and finally verifies that the shared input
was not modified. All five cases passed on T8132; the recovered guest report is
in `raw/tgmem-param-01/guest-result.txt`.

Across the four dynamic cases:

- CDM bytes are identical.
- State bytes are identical.
- Archive bytes are identical.
- Launch bytes are identical after normalizing one four-byte word.
- That word is exactly `(threadgroup_memory_bytes << 2) | 0x80`:

| bytes | launch word |
| ---: | ---: |
| 128 | `0x00000280` |
| 256 | `0x00000480` |
| 512 | `0x00000880` |
| 1024 | `0x00001080` |

The initially suspicious changing byte in the resource record is not
threadgroup metadata. The record begins with the input and output buffer
pointers. The test allocates a fresh 4-KiB output for each case, so the second
pointer naturally advances from `...35500` through `...39500`. After
normalizing that caller pointer, the resource pages are identical.

The native static control contains the same `0x280` allocation value, at a
different location because its opaque wrapper has a different argument shape.
Mesa does not need to preserve that static/dynamic distinction: its temporary
carrier can consistently use the dynamic-allocation contract for both static
and variable GLSL shared memory.

Most importantly, the current eight-buffer superset launch already contains
the same structural marker followed by a zero allocation word. Patching only
that word to `0x280` kept the existing non-shared eight-buffer workload exact
on T8132:

`/home/nsheth/Projects/asahi/logs/apple9_carrier8_tgmem128_launch_word_20260902.log`

This is an acceptance/compatibility proof, not yet a functional Mesa shared-
memory proof: Mesa's main still needs threadgroup load/store/barrier lowering.
It does show that shared-memory allocation can coexist with the current
eight-buffer carrier without another launch family.

## Occupancy is CDM policy, not a launch-program contract

The existing own-source register-pressure ladder found only two CDM config
values, `0x00080000` and `0x00880000`; bit 23 mirrors the compiler's two-tier
occupancy classification. It is not a raw GPR-count field and not a simple
threshold on the largest register number. The same apparent register footprint
can fall on either side according to live-range structure.

An ablation cleared bit 23 on a carrier captured in the high tier. The full
output remained exact and completion remained normal:

`/home/nsheth/Projects/asahi/logs/apple9_carrier8_cdm_low_20260902.log`

For correctness-first bring-up, the tested low tier is therefore conservative.
For performance, Mesa should eventually derive the tier from its own
post-allocation live-register/occupancy calculation. Neither choice changes the
opaque launch program.

## Result

None of these three features requires another opaque launch-program family:

1. Indirect dispatch is a CDM mode plus normalized hidden geometry.
2. Threadgroup memory is a patchable launch allocation word.
3. Occupancy is a one-bit CDM policy selected from compiler allocation data.

The temporary five-carrier model can therefore continue converging on one
eight-buffer superset carrier. The remaining functional gate for shared memory
is ISA/compiler support, not another packaging blob. Indirect metadata should
be corrected in Mesa before exposing general indirect dispatch, and occupancy
should remain a conservative fixed tier until the allocator exports an
evidence-backed class.

Run the structural checker with:

```sh
python3 analyze_parameter_matrix.py
```
