# EXP-M4-27 results: native Apple9 vector SSBOs

The forward and reverse fresh-process matrices both completed all seven cases.
The fail-closed analyzer independently rebuilt every 4-KiB input and output
oracle, checked the complete input/output mappings, and found every normalized
package field byte-identical between the two run orders.

Reproduce the audit with:

```sh
python3 analyze.py \
  raw/runs/m4-20260830-vector-forward \
  --repeat raw/runs/m4-20260830-vector-reverse \
  > raw/runs/m4-20260830-vector-analysis.json
```

The analyzer gates the exact source manifest SHA-256
`ee95cef3efd9b757b2adc7ff43437dc7277083a33869e6cfecbb3184a7b7498c`
and build-metadata SHA-256
`51308f1dcf27968c5ea79888d6602883804f94a6e6e19953dad856ee244d2f1d`.

## Stable package layout

Every case has the same fixed package locations:

| Object | Address/offset | Evidence |
| --- | ---: | --- |
| Archive | `0x10000000000` | Fixed-USC mapping |
| Sized block | archive `+0x340` | First word is block size |
| Constant block | archive `+0x380` | 64 bytes, common SHA-256 `9baa760c...fd27` |
| Main | archive `+0x3c0` | Block-relative `+0x80` |
| Optional state | `0x10000018000` | Decoded compact launch pointer |
| Launch | `0x10000090000` | First `0x100` bytes audited |
| Direct CDM | `0x100000b0000` | 48 bytes, common SHA-256 `d7dbd6c1...65b4` |
| Resource table | `0x100000e14a0` | Input pointer, output pointer, then zero |

The archive header is common (`9be8f59a...97cc`).  Normalizing the two resource
pointers to slots 1 and 2 gives the same 64-byte table in every case
(`04dbf448...eb01`).  The copy controls happened to allocate their input and
output at fixed-USC `+0x18000/+0x19000`; the other cases used
`+0x30000/+0x31000` because `+0x18000` held state.  These caller addresses are
resource-table values, not shader-encoding differences.

| Case | Block | Main bytes / SHA-256 | Launch STOP extent / aligned allocation | Call field | Launch SHA-256 | Structural register-copy entries |
| --- | ---: | --- | --- | ---: | --- | ---: |
| `scalar_copy` | `0xc0` | 36 / `67a99096...6199` | `0x88 / 0xc0` | `+0x28` | `c669766f...60d` | 4 |
| `uint2_copy` | `0xc0` | 36 / `d0a945ca...c755` | `0x88 / 0xc0` | `+0x28` | `c669766f...60d` | 4 |
| `uint4_copy` | `0xc0` | 36 / `1afdc395...4a9e` | `0x88 / 0xc0` | `+0x28` | `c669766f...60d` | 4 |
| `uint2_alu` | `0xc0` | 56 / `844e6b6e...513d` | `0xb6 / 0xc0` | `+0x46` | `e111c468...753f` | 8 |
| `uint4_alu` | `0x100` | 116 / `43ab8ac0...cb6` | `0xd4 / 0x100` | `+0x54` | `e5cc8797...6b9` | 12 |
| `uint2_store_x` | `0xc0` | 64 / `ae0b5a34...9068` | `0xb6 / 0xc0` | `+0x46` | `b58183f9...ca91` | 8 |
| `uint4_store_yw` | `0x100` | 70 / `a6939217...5330` | `0xb6 / 0xc0` | `+0x46` | `b58183f9...ca91` | 8 |

“Structural register-copy entries” counts the repeated four-byte launch
records ending in `09 04`/`09 44`; it is deliberately not named as shader GPR
count without an independent encoding experiment.  The extent is the terminal
STOP plus four bytes followed by an all-zero tail.  The allocation is its
established 64-byte alignment.

The partial-store launch is byte-identical to the already captured
`load2_far`/`load2_off256` launch.  `uint2_alu` differs from that launch at
exactly `+0x4c` (`04` versus `00`).  No semantic name is assigned to this byte.

## Vector memory evidence

The decisive result is that a whole `uint2` or `uint4` copy does not scalarize.
Each 36-byte main contains exactly one 14-byte device load and one 14-byte
device store:

| Width | Device load at `+0x04` | Device store at `+0x12` |
| --- | --- | --- |
| scalar | `6710440000012000510100404600` | `e700560001012100110000901100` |
| `uint2` | `6710440000022000590100404800` | `e700560001022100190000101200` |
| `uint4` | `6710440000042000570100404000` | `e700560001042100170000101000` |

The scalar/`uint2`/`uint4` copy mains differ only at
`0x0, 0x9, 0xc, 0x10, 0x17, 0x1a` and one or both of `0x1d..0x1e`.
The launch, archive header, constant, CDM, absent-state contract, and normalized
resource table are otherwise identical.  This is a particularly clean basis
for adding width-specific load/store encodings without changing packaging.

`uint2_alu` and `uint4_alu` retain their copy control's exact load access token
and format tail.  Their stores change the producer form from byte 2 `0x56` to
`0x54` but retain the width-specific format/descriptor tails.  Exact boundaries
are:

- `uint2_alu`: entry 4, load 14, two opaque 10-byte ALU instructions, store 14,
  STOP 4.
- `uint4_alu`: entry 4, load 14, eight opaque 10-byte ALU instructions, store
  14, STOP 4.

The analyzer reports every raw instruction and field without promoting the
remaining opaque ALU bytes into unsupported semantics.

## Partial stores are read/modify/write

Neither partial case is evidence for a native masked store.  Both mains read
binding 1 before writing binding 1, and their final store has the same
width-specific format and descriptor tail as the complete-vector copy.

`uint2_store_x`:

```text
+0x04  6710540000052000518100404800   binding-0 load
+0x12  6700440201052000190000404800   binding-1 load
+0x20  0b010e09020a00800000           opaque ALU
+0x2a  1b040920                       opaque pack/routing instruction
+0x2e  e700540001052100190000101200   full uint2-format binding-1 store
```

`uint4_store_yw`:

```text
+0x04  67105408000720005d0100404000   binding-0 load
+0x12  6700440001072000570100404000   binding-1 load
+0x20  9f015602021820a81701           opaque ALU
+0x2a  3b090e0b020a00000000           opaque ALU
+0x34  e700540001072100170000101000   full uint4-format binding-1 store
```

The `uint4` binding-1 load has the same access token and format tail as the
whole-`uint4` copy load.  The `uint2` partial route uses distinct load tokens,
so its component-load width is left unnamed, but the binding-1 read plus the
complete `uint2` store and exact retention of every `.y` word establish the
read/modify/write behavior.

The exact state literals start at state `+0x20`:

- `uint2_alu`: `0x11111111, 0xa5a55a5a`.
- `uint4_alu`: `0x01020304, 0x0ff00ff0, 0x11223344, 0x55667788,
  0x55aa55aa, 0x76543211, 0xa55aa55a, 0xf00ff00f`.
- `uint2_store_x`: `0x6d5a4b39`.
- `uint4_store_yw`: `0x13579bdf, 0x2468ace0`.

## Repeatability qualification

Every normalized package byte, main, state, resource table, and raw oracle is
identical between forward and reverse order.  Six cases also have identical
complete precommit BO sets.  The forward `uint4_copy` dump contains fourteen
additional overlapping fixed-USC alias views beginning at `+0x19000`; the
reverse run omits those redundant views.  All shared BO images are identical,
the actual input/output mappings and package fields are present in both, and
both complete output oracles pass.  The analyzer records this allocator/dump
variation but does not mistake redundant alias enumeration for package state.
