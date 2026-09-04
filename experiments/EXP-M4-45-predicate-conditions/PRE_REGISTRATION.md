# EXP-M4-45: predicate comparisons and arbitrary Boolean conditionals

This experiment uses only our own MSL, its `_agc.main`, public Metal APIs, and
the existing clean-room hardware testbed.  It does not inspect Apple helper,
wrapper, or framework binaries.

## Questions

1. Does the six-byte predicate compare directly encode all six relational and
   equality relations for float, signed integer, and unsigned integer inputs?
2. Is byte 1 bit 7 the complement control inferred by the earlier compile-only
   cross product?
3. Does byte 2 low bit select relational versus equality comparison?
4. Does byte 4 use the same type/direction condition-code map as compare-select?
5. How does native Metal lower nontrivial Boolean conditions when actual masked
   control flow is required?

## Gates

- Every native case must be inspected at the generated-instruction level.
- Every successfully compiled native case must execute with an exact lane-wise
  oracle.
- Field claims require an unmodified control, a sensitivity-positive splice,
  and a distinguishable mixed-true/false input vector.
- Ordinary value-only diamonds are controls, not evidence about execution-mask
  predicate lowering.
- A mutation arm stops after two genuine hangs.

## Initial hypotheses

- `cmpmode`: low nibble 2 is ordered relation and 3 is equality.
- byte 1 bit 7 complements the base comparison, accounting for `<=`, `>=`, and
  `!=`.
- byte 4 low bits select float/unsigned/signed and greater/less direction.
- Compound Booleans will either become nested mask regions (short-circuit form)
  or a materialized Boolean followed by compare-to-zero; this experiment does
  not assume which.

## Falsifiers

- A native relation whose field changes do not fit the proposed factorization.
- A valid field mutation whose complete output contradicts the proposed
  semantics.
- An arbitrary Boolean form requiring a separate predicate-producing opcode or
  a nonzero predicate destination.
