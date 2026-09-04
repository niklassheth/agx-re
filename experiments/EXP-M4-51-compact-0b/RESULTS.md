# EXP-M4-51: Atomic-prep records and pending-input/returned-result slots

## Question

Native Metal sometimes places `0b 00 00 02` or a ten-byte low-`b` record
immediately before a device atomic.  These records had been named
`DEVICE_ATOMIC_PREP`, suggesting that a returning atomic might require them to
transfer a pending input into a pending result.  This experiment tests that
claim directly.

All shaders are own-source MSL.  Only `_agc.main` bytes were compared or
mutated.  Every hardware verdict compares the complete output buffer against
an independent CPU oracle; command-buffer retirement alone is not a pass.

## Corpus census

`analyze_corpus.py` scanned 35,163 public-source native archives containing
30,560 unique compute mains.  A raw scan, used because many large programs are
not completely decoded yet, found 878 plausible device-atomic packets:

| Immediate predecessor | Instances |
|---|---:|
| none of the candidate low-`b` forms | 712 |
| exact compact `0b 00 00 02` | 132 |
| a ten-byte low-`b` form | 34 |

All 132 compact occurrences precede an atomic whose input dependency mask is
slot 1.  This is strong evidence that the compact record participates in one
Metal-selected slot-1 operand schedule.  It is not evidence that atomics in
general require a prep record.

The ten-byte class is not atomic-specific.  The public corpus contains more
than 1,500 occurrences of the common byte-2-`0x06` forms, broadly followed by
control-flow, moves, and ALU instructions.  Only four occurrences of the
exact device form `0b 00 06 00 20 00 00 14 00 00` are directly followed by an
atomic in this corpus.  The old `tg_atomic_prep10` name is therefore historical
and too specific.

## Hardware experiments

### A prep-free pending-input atomic

An own-source scalar load publishes a distinguishable operand in slot `S`.
The following returning device atomic names `S` in its six-bit input dependency
mask and later publishes its old-value result in slot `R`.  The oracle checks:

- the operand read by the atomic;
- the old value returned by it;
- the final atomic target;
- retained later consumers of both input and result.

The final carrier issues six loads and six returning atomics concurrently.  It
keeps the occupied slot set exactly `{1,2,3,4,5,6}` and permutes which pending
input reaches each native returned-result slot.  This preserves a coherent
scoreboard allocation schedule rather than forcing an isolated producer into
an arbitrary slot.

Every compact and ten-byte prep record was replaced with an ordinary,
independently known instruction of the same length writing unused `r60`.

| Test | Executions | Result |
|---|---:|---:|
| Unmodified baseline | 6 | exact |
| Remove each of six native prep records separately | 36 | exact |
| Remove all six native prep records | 6 | exact |
| All `S,R in 1..6`, forward order, three repeats | 108 | exact |
| All `S,R in 1..6`, reverse order, two repeats | 72 | exact |

The matrix includes all six `S == R` cells.  Reusing the consumed input slot
for the returned result is legal without either prep form.

The native carrier covers add, subtract, XOR, OR, AND, and exchange atomics,
32 lanes, simultaneous slot pressure, retained old values, and subsequent
loads of all final targets.

### Removal-control pitfall

The first removal control used a compact instruction believed to write a dead
`r15`.  It actually overwrote this carrier's still-live pending `r15` operand
and corrupted that atomic.  `results.json` in `six_pending_prep_removal` is
retained as a superseded harness failure; `results2.json` uses verified-unused
`r60` and is the valid result.  This is also why zero padding was not used:
all-zero words fault rather than acting as free-standing NOPs.

### Why an isolated 6x6 fanout sweep was misleading

An earlier single-atomic mutation changed its result-publication record and
first consumer together.  Only native slot 6 passed; slots 1--5 consumed too
early and observed the addend without the old value, although later GPR stores
and final memory were correct.  This is a sensitivity-positive result: an
isolated first return cannot simply be assigned an arbitrary slot.  It does
not make prep mandatory.  The coherent six-producer permutation above is the
valid `S x R` test.

Likewise, a direct device store of the returned GPR passed all naive `S x R`
mutations, but that store can obtain the eventual value through its associated
GPR and does not prove that the mutated publication slot was scheduled
correctly.  Those 225 executions are retained as supporting data, not the
closure result.

## Conclusion

`DEVICE_ATOMIC_PREP` is not an atomic correctness protocol and is not required
for the direct-pending returning path:

```text
device load publishes slot S
atomic input dependency mask names S
atomic result record publishes on a valid scheduled slot R
```

This works for every `S,R in 1..6`, including `S == R`, without prep.  The
compact `0b 00 00 02` is an optional compiler-selected staging/scheduling form
correlated with a slot-1 input.  The ten-byte low-`b` record belongs to a broad
instruction family and is likewise removable from every native atomic schedule
tested.  Their exact performance/cache/register-lifecycle effects remain
unresolved; no correctness claim requires inventing one.

Compiler consequence: Mesa's current materialized-GPR, dependency-mask-zero
path remains valid.  A future direct-pending path should connect the producer's
actual slot to the atomic dependency mask and let the normal scoreboard
allocator schedule the returned result.  It must not emit either prep record
as a mandatory transfer pseudo.

## Artifacts

- `CORPUS_CENSUS.json`: raw and decoded corpus counts and witnesses.
- `atomic_prep_slots.metal`: all own-source workloads.
- `build_six_pending_prep_removal.py`: same-length removal controls.
- `build_six_pending_slot_cross.py`: coherent 36-cell slot permutation.
- `run_six_pending_prep_removal.py`: exact hardware runner.
- `work/six_pending_prep_removal/results2.json`: 48 exact removal runs.
- `work/six_pending_slot_cross/results.json`: 108 forward-order runs.
- `work/six_pending_slot_cross/results_reverse.json`: 72 reverse-order runs.
- `work/pending_atomic_fanout/results.json`: isolated-publication negative
  control.
- `work/pending_atomic_cross/results.json`: direct-store supporting control.
