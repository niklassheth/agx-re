# EXP-M4-53 results: predicate bank and mask stack are separate

## Result

The varying compare and mask-consumer fields are real, but the earlier model
attached them to the wrong state.

Apple9 has a **six-entry predicate scratch bank** and a separate implicit
**execution-mask/reconvergence stack**.  Ordinary nested conditionals do not
consume one predicate bank per nesting level: Metal compares into bank 0,
immediately pushes that result into the mask machine, and then freely reuses
bank 0 inside the nested region.  That is why EXP-M4-52 reached 32 live `if`
scopes with constant compare/push fields.

Nonzero fields appear when several Boolean results overlap in lifetime, most
visibly in nested/compound loop control.  They select the scratch bank, not the
depth of the saved execution-mask stack.

## Predicate producer/consumer cross

The own-source `u_lt` carrier has one comparison and one conditional push.
Keeping its truth function and all operands fixed, the test crossed the
comparison's bank field with the push source field.

| Compare bank | Matching push source | Exact 16-word output |
|---:|---:|---|
| 0 | 0 | pass |
| 1 | 1 | pass |
| 2 | 2 | pass |
| 3 | 3 | pass |
| 4 | 4 | pass |
| 5 | 5 | pass |

Six tested off-diagonal pairs all completed but failed, producing an empty
true arm in this carrier.  Therefore neither field is an ignored hint and the
matching relation is not an alias.

The encoding is:

```text
compare byte 0 = 0x0a | (bank << 5) | (producer_invert ? 0x10 : 0)
push byte 3    = 0x01 | (bank << 2) | (consumer_invert ? 0x20 : 0)
```

Consumer inversion remained orthogonal on banks 0, 1, and 4: every lane
matched the complemented oracle.

The two remaining push source encodings are special values, not predicate
banks:

| Push source | Result under the current active mask | With bit `0x20` |
|---:|---|---|
| 6 (`0x19`) | true / identity | false / empty |
| 7 (`0x1d`) | false / empty | true / identity |

Those results were obtained with an ordinary bank-0 comparison still present,
so the constants do not come from attempting to write comparison destinations
6 or 7.  Comparison encodings 6 and 7 were syntactically accepted but have no
observable matching predicate consumer and must not be allocated.

## Loop consumer cross

The `pc_base_probe` latch independently proves the same bank relationship:

| Compare bank | Loop-update bank | Result |
|---:|---:|---|
| 0 | 0 | exact 64-word pass |
| 1 | 1 | exact 64-word pass |
| 2 | 2 | exact 64-word pass |
| 1 | 0 | watchdog hang |

The pair can therefore be relocated without changing mask-stack depth.  This
directly refutes the old name `LOOP_MASK_DEPTH` for the selector subfield.

The old `LOOP_MASK_USE_PREDICATE` name for bit `0x20` was also too vague.  On
the native bank-0 latch:

```text
compare normal + update bit 0x20 set       exact
compare inverted + update bit 0x20 clear  exact
compare normal + update bit 0x20 clear     changed output
```

Two inversions cancel, so bit `0x20` is a predicate-consumer polarity control
in the tested loop-update form.  This also explains why Metal can choose
`0x02` for one normalized loop condition and `0x22` for another without
changing loop depth.

## Native-corpus check

An exact-leader census of 35,332 compute pipelines from the own/public-source
EXP-M4-32 corpus found conditional push sources 0 through 5 in both normal and
inverted forms.  It found no source-6 or source-7 conditional push.  The
separate loop-scope tail `0x1a` was excluded from the conditional counts.  Full
counts are in `CORPUS_CENSUS.json`.

This census also exposes why scanning every byte ending in `0xa` was invalid:
the six-byte comparison leader overlaps several still-incompletely-decoded ALU
forms.  Apparent compare destinations above the six-bank range were not paired
with corresponding control consumers and are decoder false positives or
ambiguous forms, not evidence for a 16-entry predicate file.

## Compiler model

- Model six allocatable predicate banks, numbered 0 through 5.
- Treat producer and consumer polarity as independent fields.
- Model sources 6 and 7 only as hardware constants if a future optimization
  needs them; Metal did not select them in the measured corpus.
- Emit ordinary `if` comparisons and pushes through bank 0 regardless of
  nesting depth.
- Track nested `if` structure only in the software CFG stack and the hardware
  push/else/pop stack.
- Allocate nonzero predicate banks only for overlapping Boolean lifetimes,
  such as loop-control expressions.  Do not derive the bank from total mask
  nesting depth.

## Artifacts

- `PRE_REGISTRATION.md`: hypotheses and decisive crosses.
- `run_ablations.py`: archive mutations, watchdogs, and exact CPU oracles.
- `raw/ablation_results.json`: complete hardware output and diagnostics.
- `CORPUS_CENSUS.json`: exact native conditional-push populations.
- `PREDICATE_BANK_MODEL.json`: concise machine-readable model.

Environment: Apple M4/T8132, macOS 26.6.2 build 25G83.
