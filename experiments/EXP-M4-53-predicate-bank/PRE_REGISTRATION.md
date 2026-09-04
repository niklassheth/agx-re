# EXP-M4-53: predicate bank versus execution-mask stack

## Question

Apple9 comparisons have a varying field in byte 0 and execution-mask pushes
have a varying selector in byte 3.  Earlier work called the former a predicate
destination and derived both fields from conditional nesting depth.  Native
Metal's depth-32 ordinary-if corpus disproves the nesting rule: every level
uses the same compare and push encodings.

This experiment asks the narrower machine question: do the two varying fields
address a real, independently selectable predicate bank, or were they
misidentified?

## Controls and mutations

The carrier is the own-source `u_lt` kernel from EXP-M4-45.  It contains one
unsigned comparison, one mask push, distinguishable true/false lanes, and a
complete 16-word output oracle.

1. Keep the comparison's truth function fixed while setting its byte-0 bank
   field to each even encoding `0, 2, ..., 14`.
2. Set the push selector to the corresponding sequence `1, 5, ..., 29`.
3. Run off-diagonal controls in both directions.
4. Repeat selected diagonal cases with push bit `0x20`, whose inversion
   behavior was independently established by EXP-M4-45.
5. Re-run the unmodified control between groups.

The decisive result is a diagonal compatibility relation.  If bank `B` works
only with selector `1 + 4*B`, the fields form an addressed producer/consumer
pair.  If all combinations work, one or both are likely hints or aliases.  If
only the native zero pair works, the nonzero loop encodings require a different
model.

As a secondary test, the outer-loop latch in EXP-M4-46 is mutated from the
native compare/update pair `(0, 0x22)` to `(1, 0x26)` and `(2, 0x2a)`, both
jointly and one field at a time.  This checks whether the same relationship is
usable by the loop-mask operation.  Because a wrong loop update can hang, this
arm stops after the first genuine watchdog timeout.

## Interpretation boundary

Even a positive predicate-bank result does not make that bank the execution-
mask stack.  The implicit push/else/pop stack and the short-lived comparison
bank are separate state until hardware evidence shows otherwise.
