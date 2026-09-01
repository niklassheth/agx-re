# EXP-M4-35 results

## Result

Native Metal consumes pending scalar device loads directly with Apple9 integer
XOR.  It does not insert a min/max or arithmetic materialization bridge.  The
extended `ilogic` instruction carries the same logical scoreboard slot as FALU, but
its machine representation is different: it is a six-bit one-hot mask rather
than FALU's three-bit binary slot number.

| Pending slot | `ilogic` instruction bit |
|---:|---:|
| 1 | 45 |
| 2 | 46 |
| 3 | 47 |
| 4 | 61 |
| 5 | 62 |
| 6 | 63 |

Equivalently, bits 45--47 hold the low three mask bits and bits 61--63 hold
the high three.  Slot 0 is an all-zero mask.

## Evidence

Eight own-source kernels were freshly compiled and executed on T8132/macOS
26.6.2 build 25G83.  Every complete 4-KiB output matched its independent
oracle.  The direct cases cover:

- one scalar device load XOR an ordinary computed value;
- two pending loads from distinct bindings;
- two pending loads from one binding;
- retained load values with a later integer-add consumer; and
- five- and six-load chains occupying the allocator slots.

In the six-load chain, native issue order produced scalar-load tokens
`5101,1100,5100,9100,d100,1101`, which are slots `6,1,2,3,4,5`.  The six
corresponding logic instructions carried masks `0x20,0x01,0x02,0x04,0x08,0x10`.
This observes every mask bit with one exact shader and rules out a binary
field interpretation.

The two-load kernels give both loads the slot-6 producer token `5101`; the one
logic consumer has bit 63 set.  Its ordinary source descriptors still identify
the two distinct GPR destinations, matching the established scoreboard-group
model.

## Compiler consequence

The earlier Mesa experiment wrote the binary value `6` into bits 45--47 of
`ilogic`.  That selected mask bits 2 and 3 rather than slot 6, so the load
results read as zero.  The temporary `UMIN(x, x)` bridge avoided the bad logic
encoding but was not native behavior.

The correct lowering is:

1. Let the hardware-validated integer XOR form be a first handoff for a
   pending scalar-load group.
2. Allocate the group with the existing shared six-slot allocator.
3. Write exactly one of bits 45--47 or 61--63 for that slot.
4. Keep source retain/release state orthogonal to the one-hot pending mask.
5. Use an all-zero mask for an ordinary GPR-only logic operation.

`analyze.py` re-extracts every stage main, verifies full outputs, and gates the
complete producer-token and one-hot-mask sequences.  Detailed records and
hashes are in `RESULTS.json`.
