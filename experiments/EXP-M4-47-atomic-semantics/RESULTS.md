# EXP-M4-47: Apple9 atomic semantics

## Scope

This is a clean-room, own-source Metal experiment on T8132/macOS 26.6.2
(25G83). It varies atomic operation, address, result use, contention, and
control flow while retaining exact CPU output oracles. It does not inspect the
proprietary launch program or other Apple binaries.

The source corpus is `atomic_semantics.metal`; `run_native.py` builds and runs
each named function in a fresh process. `native_results.json` records complete
readback and oracle data. The extracted own-source stage mains and structured
decoder output are under `archives/` and `raw/native_analysis.json`.

## Executed coverage

All 21 cases passed exact hardware validation:

- Device `add`, `sub`, `and`, `or`, `xor`, unsigned/signed `min` and `max`,
  exchange, compare-exchange, and floating add.
- Returning and discarded operations, return fanout, dynamic addresses,
  divergent conditionals, loops, and 16-way contention.
- Threadgroup contention, integer operations, and compare-exchange.

The output checks include every returned and final word for private-address
cases. Contention checks use the exact final value plus the permutation of all
old values, rather than assuming a lane execution order.

## Device atomic form

The per-lane device-memory form is 14 bytes and begins with `0x67`. The native
operation selector is in byte 12 as `(op << 1) | 0x40`:

| Operation | selector |
|---|---:|
| add | `0x10` |
| and | `0x11` |
| compare-exchange | `0x12` |
| float add | `0x13` |
| signed max | `0x14` |
| signed min | `0x15` |
| or | `0x16` |
| sub | `0x1b` |
| unsigned max | `0x1c` |
| unsigned min | `0x1d` |
| exchange | `0x1e` |
| xor | `0x1f` |

The ordinary materialized-input form uses byte 2 `0x54`. The input data GPR is
split across byte 5 bit 7 and byte 6 bits 0–5. The address index uses byte 5
bits 0–6. Compare-exchange consumes an adjacent two-register tuple ordered as
`desired, compare`, even though NIR presents `compare, desired`.

Returning operations use byte 9 `0x02` and publish an asynchronous result.
EXP-M4-49 subsequently established the adjacent result record's full `r0..r63`
destination and slot-1--6 publication fields. EXP-M4-50 established that
atomic-packet bits 12--17 are instead an input dependency mask: ordinary
materialized inputs use mask zero and directly pending inputs name their
producer slot. Discarded operations use byte 9 `0x40` and publish no result.

The earlier Mesa prototype also treated `0b 00 00 02` as unconditional atomic
prep. EXP-M4-50 disproved that compiler model: removing the invented pseudo and
using a zero input mask made the complete returned-atomic hardware suite exact.

The device atomic destroys or releases its address/data inputs in the tested
last-use form. A general SSA compiler must either encode the still-live forms
or give the instruction private dead copies. The initial Mesa implementation
does the latter.

## Threadgroup form

Threadgroup atomics use a distinct 12-byte memory form. The same five-bit
operation selectors recur, which is strong evidence that operation semantics
are shared while address-space and publication fields differ. Threadgroup
loads, stores, barriers, allocation, and atomics were executed here, but Mesa's
Apple9 compiler does not yet model the surrounding threadgroup-memory system;
this experiment therefore does not justify treating the 12-byte form as a
drop-in device-atomic encoding.

## Compiler boundary

The implemented Mesa slice is the scalar 32-bit SSBO atomic family. It maps
normal NIR atomics to a semantic VIR operation, allocator-owned address/data
values, an adjacent compare-exchange tuple, and a normal writable resource.
It does not embed capture-assigned registers or replay bytes. Unsupported
floating min/max, floating compare-exchange, wrap increment/decrement, and
threadgroup atomics remain explicit future work.
