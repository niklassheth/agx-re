# EXP-M4-25 results: native T8132 add3 package

## Verdict

The complete native M4 package for the own-source kernel
`out[i] = a[i] + b[i]` was captured and executed exactly.  The canonical
arm64e run produced 64/64 bit-exact float outputs, preserved both complete
input buffers, and preserved all 768 output-guard bytes.

The package was repeated in an independent process.  All 28 caller-owned BO
images in the pre-commit snapshots were byte-identical across the two runs.

## Exact package

At the fixed USC base `0x10000000000`, the relevant native graph is:

| Object | Address / offset | Exact observation |
|---|---:|---|
| Archive header | `+0x00000..+0x0033f` | `0x340` header, two tables of ten helpers plus two terminals |
| First block | `+0x00340` | block size `0xc0` |
| Constant program | `+0x00380`, 64 bytes | SHA-256 `9baa760c5185b9e5645bd1299e5ec948674258d6cbb0dc68b1394f1e45f3fd27` |
| Own shader main | `+0x003c0`, 56 bytes | SHA-256 `8bca649243127f0a1790e51fb39c0bcb3f0229bb06e3131fc875511b46c100b7` |
| First dynamic state | `+0x18000`, 64 bytes | byte zero is `0x40`; remaining bytes zero |
| Launch wrapper | `+0x90000`, `0xc4` bytes in a `0x100` allocation | SHA-256 `86b23ba7a8e7b030d6e813846461d6695bf98c60233a44e49a78fb34b36a9f0c` |
| CDM record | `+0xb0000`, `0x2c` bytes | SHA-256 `d38addedfeff55e15ab9444b6ac3b027b508789402898f2299105b1ea716671b` |
| Resource table | `+0xe14a0` | three LE qwords: `+0x30000`, `+0x30400`, `+0x30800` |

The pre-commit CDM tail at `+0xb002c` is zero.  Commit appends the ordinary
`0x40000000` terminator; the `0x2c` record itself does not change.

## Mesa comparison

Mesa's existing three-buffer main, constant program, launch relocation,
dynamic-state record, resource table, and direct CDM encoder all reproduce
the native T8132 bytes.  The one discrepancy was archive helper count:

- Native T8132 uses ten helper records in each header table.
- The branch used six for add3 because that value came from the G17 package.
- Both the native T8132 one-buffer and three-buffer profiles use ten.

The Mesa profile was corrected to ten helpers and the package tool now checks
the complete native first block, state, aligned launch allocation, resource
record, and CDM record byte-for-byte.  This also removes the artificial helper
ABI mismatch between the one-buffer and three-buffer compute profiles.

The evidence does not establish that every later archive block in Metal's
process-wide compiler cache is needed by this kernel.  Mesa intentionally
constructs only the caller-owned first block and the referenced dispatch
objects.

## Reproduction gate

`python3 analyze.py` verifies the two snapshots, the independent-process
repeat, exact raw results, immutable inputs, guard bytes, package structure,
and all hashes above.  It reads only our own shader/package data and public API
outputs.
