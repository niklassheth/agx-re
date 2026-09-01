# EXP-M4-36 results: direct stores select pending values by GPR

## Result

Apple9's direct pending-result `device_store` form (`addr_mode = 0x56`) does
not contain an ordinary scoreboard-slot selector and is not implicitly tied to
slot 6.  Store byte 3 names a half-register/GPR destination, and hardware
obtains the pending load value associated with that destination.

This was established on T8132 under macOS 26.6.2 build 25G83.  Fourteen
whole-program cases ran three times each.  All 42 command buffers completed,
all 42 execution canaries were exact, and there were no faults or hangs.

The native corpus gives a stricter compiler-facing rule.  The reproducible
high-confidence census selects adjacent load/store pairs whose `0x56` store
names the same half-register and uses the matching data format.  All **40/40
unique pairs**—representing **208 native occurrences**—publish the load through
slot 6.  No slot-1--5 native direct pair is present in that subset; see
`NATIVE_DIRECT_PAIR_CENSUS.json`.

Two input words were deliberately distinguishable:

```text
A = 0x11111111, load destination r0
B = 0x22222222, load destination r1
```

For every valid two-pending schedule, stores naming `r0,r1` wrote `A,B`, while
stores naming `r1,r0` wrote `B,A`:

| Load issue/publication schedule | Store selectors | Exact output | Repeats |
|---|---|---|---:|
| A→r0/slot6, B→r1/slot1 | r0, r1 | A, B | 3/3 |
| A→r0/slot6, B→r1/slot1 | r1, r0 | B, A | 3/3 |
| B→r1/slot6, A→r0/slot1 | r0, r1 | A, B | 3/3 |
| B→r1/slot6, A→r0/slot1 | r1, r0 | B, A | 3/3 |
| A→r0/slot1, B→r1/slot6 | r0, r1 | A, B | 3/3 |
| A→r0/slot1, B→r1/slot6 | r1, r0 | B, A | 3/3 |
| A→r0/slot6, B→r1/slot2 | r0, r1 | A, B | 3/3 |
| A→r0/slot6, B→r1/slot2 | r1, r0 | B, A | 3/3 |

The producer issue order, producer tags, and store selectors were therefore
independently varied.  The value always followed the store's GPR selector,
not the first-issued result, most-recent result, or slot-6 result.  Both store
orders succeeded, so consuming one pending result does not destroy the other.
The `slot6 + slot2` case also proves that direct stores tolerate a hole at slot
1 in this two-result construction.

## Scalar-load head constraint

There is a separate producer-allocation constraint.  A single load published
through slot 6 stored exactly from both r0 and r1.  The same isolated load,
with only its producer tag changed to slot 1 or slot 2, stored zero:

| Isolated producer | r0 store | r1 store | Repeats |
|---|---:|---:|---:|
| slot 6 | A | A | 3/3 each |
| slot 1 | 0 | 0 | 3/3 each |
| slot 2 | 0 | 0 | 3/3 each |

The canary remained `0x0000005a` in every zero case, excluding non-execution.
Slots 1 and 2 are not intrinsically unsupported by direct store: each worked
exactly in a pending set that also contained a slot-6 scalar load, including
when the slot-1 producer was issued before the slot-6 producer.  The evidence
therefore supports a scalar-load group/head constraint, not an implicit
slot-6 selector in the store.  This experiment does not identify the physical
reason for that constraint.

## Compiler consequence

Although the synthetic experiment shows a broader hardware mechanism, the
initial compiler should deliberately implement only the native-observed
subset:

1. Emit a direct `0x56` load-to-store handoff only when that load owns slot 6.
2. Preserve each pending result's destination GPR until its direct store.
3. Encode store byte 3 as twice that GPR number (the half-register index).
4. Materialize a slot-1--5 result through a proven slot-bearing consumer before
   storing it, even if another slot-6 load is pending.
5. Model the restriction as an admission rule, not a physical slot field in
   the store encoding; byte 3 remains the GPR selector.

This leaves the wider synthetic result documented for later, without making
the first compiler depend on behavior Metal never emits.  Other load/store
widths and vector forms still require their own encoding evidence.

## Evidence

- Machine-readable cases: `generated/cases.json`
- Native direct-pair census: `NATIVE_DIRECT_PAIR_CENSUS.json`
- Complete run records: `captures/t8132-25G83-20260901/results.json`
- Per-case stdout, stderr, and result records under the same capture directory
- Target metadata: `captures/t8132-25G83-20260901/target.txt`

SHA-256:

```text
generated/cases.json
  aa0f6ac4821019395e99976550bd340f53cb373f8180bf00fb0df5d2dec6864d
captures/t8132-25G83-20260901/results.json
  19b0fb7db6e054aebbe54ce42edbef1e8e3f35cacf3b69a53061dfabd1086bd7
```
