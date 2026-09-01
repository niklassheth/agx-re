# EXP-M4-15: Apple9 compare/select and literal-pool ABI

## Scope and method

This experiment compiled the caller-owned `compare_select.metal` kernels at
runtime on an M4/T8132, captured only caller-visible BO mappings with the
existing iotrace mechanism, and changed one comparison relation at a time.
No Apple binary was inspected. A second source variant reversed the operands
for every non-equality relation.

The native program is 46 bytes:

```text
get_sr gid.x
isel_pool
device_load buffer(1)[selected_index]
device_store buffer(0)[gid.x]
stop
```

The 10-byte selector is:

```text
02 09 07 03 MODE TRUE CC 20 20 FALSE
```

`buffer(1)` is a three-u32 literal pool: comparison constant, true result,
false result. `TRUE` and `FALSE` are `0x81` and `0x82`, selecting pool words 1
and 2; inequality/ge forms may exchange them. The following load is always
`67 00 44 00 01 80 20 00 51 01 00 40 46 00` and the output store is always
`e7 00 56 00 00 01 21 00 11 00 00 90 11 00`.

## Condition matrix

| NIR relation | MODE | CC | TRUE/FALSE |
| --- | ---: | ---: | --- |
| `ieq` | `0x26` | `0x87` | `0x81/0x82` |
| `ine` | `0x26` | `0x87` | `0x82/0x81` |
| `ult` | `0x22` | `0x84` | `0x81/0x82` |
| `uge` | `0x22` | `0x84` | `0x82/0x81` |
| `ilt` | `0x22` | `0x86` | `0x81/0x82` |
| `ige` | `0x22` | `0x86` | `0x82/0x81` |
| `feq` | `0x26` | `0x80` | `0x81/0x82` |
| `fne` | `0x26` | `0x80` | `0x82/0x81` |
| `flt` | `0x22` | `0x82` | `0x81/0x82` |
| `fge` | `0x26` | `0x83` | `0x81/0x82` |

Reversing a relational comparison toggles CC bit zero: unsigned `0x84` to
`0x85`, signed `0x86` to `0x87`, and float `0x82` to `0x83`. Equality is
operand-order independent.

## Hardware validation

Mesa emits the selector from NIR with a fixed register schedule and supplies
the literal pool through a second source-built launch ABI. The DRM-shim test
ran 23 cases: all ten canonical relations, both operand directions, a full
32-bit comparison constant, a negative signed constant, arbitrary true/false
u32 values, and NaN cases. Every case ran two direct dispatches in each of two
append-only commands and produced exact output, queue `2/2/2`, firmware stamp
`0x200`, and fresh ordered timestamps.

T8132 float comparisons flush positive and negative subnormal operands to
signed zero. NaN is unordered: equality, less-than, and greater-or-equal are
false; not-equal is true. This is an execution semantic, not merely a compiler
encoding observation.

The experiment locates the selector form, comparison mode, condition byte,
pool indices, and operand-direction bit. It does not claim the general register
or special-file packing of bytes 1, 3, 7, or 8; that work belongs with the
future Apple9 register allocator.
