# SFU operand controls, T8132, 2026-09-04

Provenance: public-source corpus plus project-authored Metal source. Inspect
and mutate only the corresponding `_agc.main`, never launch/helper programs.

Questions recorded before new Metal measurements:

1. Is ordinary-SFU byte6 bit4 a float/half source-width selector? Native
   `0xa0` occurs in bfloat/half computations, whereas FP32 probes see zero.
2. Is ordinary-SFU bit5 destructive source release independently of width?
3. What distinguishes reciprocal's `0x00`, `0x02`, and `0x10` forms? Its
   alleged bit4 release rule may describe only one operand representation.
4. Do negate/absolute modifiers or cache/operand selection explain the
   differing fields without assigning function-specific lifetime semantics?

Collect matched float/half store, reuse, ALU-produced, negated, and absolute
inputs for reciprocal, rsqrt, exp2, log2, and floor. Inspect raw differences
before choosing controlled mutations. Record function result AND surviving
source value; arithmetic-only acceptance cannot establish release semantics.

Corpus walks stop at unknown lengths. Their prefixes are useful for discovery,
not a complete census; retain raw examples and qualify opcode candidates by
their surrounding instructions and source provenance.
