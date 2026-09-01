# EXP-M4-17 — Apple9 Dynamic-Caching operand state

This experiment separates architectural register numbers from the additional
Apple9 operand and instruction-wide state emitted by the Metal compiler.
EXP-M4-16 established the physical-register fields, but deliberately left the
cache/lifetime fields unresolved.  This follow-up does not assume that a bit
correlated with SSA liveness is a destructive "keep" bit.

`generate_lifetime_msl.py` emits caller-owned kernels in families.  Within a
family the target operation is unchanged, while the final integer consumer
keeps either a target operand or an unrelated control operand live across it.
The consumer uses `as_type<uint>` for floating-point operations so the Metal
compiler cannot reassociate it into the target arithmetic.

`analyze_lifetime.py` locates the target instruction, removes only the
independently proven physical-register fields, and reports the remaining
context word.  It also prints the full instruction and register tuple; a pair
is not treated as evidence if the intended operation or instruction form
changed.

## Clean-room boundary

All shader sources here are ours.  They are compiled at runtime through the
public Metal API in macOS launched through the repository's hypervisor
`run_guest.py` route.  Only the resulting caller-owned `_agc.main` bytes are
inspected.  No proprietary executable is disassembled or decompiled.

## Capture

On the host:

```sh
python3 generate_lifetime_msl.py work/lifetime.metal
```

Copy the source plus `tools/shdump/{shdump.m,agxparse.py}` to the macOS guest,
build `shdump`, and run `capture_guest.sh`.  Copy the resulting `*.main` files
back into `work/main/`, then run:

```sh
python3 analyze_lifetime.py work/main
```

Hardware splices derived from the result must execute through the source-built
T8132 compute runner with the register-copy workaround disabled.  Compiler
correlation alone is not sufficient to assign semantics to any cache field.

`generate_pressure_cache_msl.py` adds the eviction discriminator.  Its probes
use one caller buffer and 32, 64, or 88 loop-carried floating-point values.
The target `fmin` retains its first source across the rest of the loop body, so
changing cache/allocation fields is tested under sustained register pressure,
not merely while every value happens to remain resident.  The dynamic loop
bound is read from the final word of the same 64 KiB buffer; this preserves the
one-buffer launch ABI used by the source-built T8132 runner.

`pressure_cache_run.m` dispatches the 88-value probe through public Metal and
requests an `iotrace` snapshot after completion.  Those caller BOs provide the
matching launch/compiler-state metadata when the unmodified archive main alone
is not sufficient to execute in the source-built envelope.

## T8132 hardware results

The 88-value control executes exactly through the source-built G16 queue when
the complete caller compiler package is installed (64 KiB code BO, 16 KiB
state page, relocated launch program, and source-built resource/CDM records).
Installing only `_agc.main`, even with its exact 64-byte constant program, is
not admitted by CP.  The live code BO has nonzero bytes through `+0x5f82`, so
the one-page WRITE_ONLY test envelope is not a general compiler package.

### Device-load producer state

The Apple9 device-load destination is the descriptor at byte `+3`; for the
tested scalar loads it is `(GPR << 1)`.  The old ISA database incorrectly
called instruction bits 70 and 72 destination fragments.  They cannot be:
both bits can be changed together while the following ALU continues to read
the same GPR and produces exact output.  They are a coupled producer-state
pair.  Compiler output uses `00` and `11`; the independently generated `01`
and `10` hybrids are invalid for the tested chains.

### Float ALU/minmax consumer state

Compact float `fadd`, `fmin`, and derived `fmax` use a three-bit consumer-state
field at bits `[45:48]`.  Exhaustive T8132 tests at 256 threads per threadgroup
give this accepted matrix (`A/B` are the two load-producer state pairs):

| producer A | producer B | accepted consumer values |
|---|---|---|
| `11` | `11` | `6` |
| `00` | `11` | `1`, `6`, `7` |
| `11` | `00` | `1`, `6`, `7` |
| `00` | `00` | `1`, `7` |

This table was reproduced independently with `fadd` and `fmin`.  The `fmax`
control was made by changing only the proven min/max opcode selector in the
exact `fmin` caller package and also produced the expected max result.  A
consumer value is therefore not a standalone ALU mode: it is interpreted with
the producer state of the operands.

Bits 19 and 20 are source release/last-use state for these compact float
forms.  The apparent earlier counterexample was an operand-labeling error:
the compiler commutes `fadd`, so target source B is the source-language `a`
that is reused later.  It does not commute `fmin/fmax`, where source A is the
reused `a`.  In every case:

* changing the reused source's bit from retain (`0`) to release (`1`) makes the
  main operation itself correct but the later use read as zero;
* changing a dead source from release (`1`) to retain (`0`) is exact;
* `fadd` source-B release fails under `00/00`, `00/11`, and `11/00` producer
  pairs, with accepted consumer values 1, 6, and 7;
* `fmin` source-A release fails under the same producer combinations;
* a high-pressure `fmin` retains a source through 86 intervening updates and
  fails in the same way when that source is released.

The compact source-descriptor high bits 15/31 are separate from release state.
Flipping either descriptor bit is exact for `fadd`, `fmin`, and `fmax`; pairing
the descriptor flip with a bad release neither fixes nor changes the bad
result.  Destination-state bit 21 is also exact in both directions, including
the 88-value pressure probe.  These are strong negative results for the tested
32-bit compact float forms, not a claim that the bits are reserved in every
Apple9 instruction form.

### Compare/select

The ten-byte explicit-false select has a three-bit consumer-state field at
bits `[61:64]`.  Its correctness depends on which values come from device
loads.  With loaded compare operands and ALU-produced selected values, all
eight consumer values execute exactly.  With ALU-produced compare operands
and loaded selected values, the compiler-native load state requires consumer
value 6; values 2 and 5 can appear correct at 32--128 threads per threadgroup
but corrupt output at 192--256.  Changing both selected-value producers from
`11` to `00` and the consumer from 6 to 1 restores exact output at 256.

At that alternate known-good `00/00` + consumer-1 point, every individually
tested auxiliary bit remains exact: destination bit 21, descriptor bits
15/31/47/79, state bits 19/20/39/71, and each descriptor/state pair.  The same
mutations were also harmless in the compiler-native state.  Thus none of
those bits repairs an invalid select route or hides an eviction failure in the
tested full-occupancy case.  They remain named conservatively because their
roles in other select forms are not established.

### Integer min/max boundary

Unsigned integer min is a useful negative control.  At 256 threads per
threadgroup, destination bit 21, source descriptor bits 15/31, state bits
19/20, and all eight values of bits `[45:48]` are individually output-exact.
The integer and float min/max opcodes share a six-byte structural family, but
these control positions are not semantically interchangeable across the two
datapaths.

### Compiler rule justified by current evidence

For the supported compact float path, instruction selection must model the
coupled load-producer state, the three-bit consumer state, and per-source
last-use.  Register allocation alone is insufficient.  It is safe to preserve
compiler/native descriptor and destination-state values for now, but the
compiler must not invent meanings for them.  Select and integer min/max need
their own form-specific state models rather than inheriting the float rule.
