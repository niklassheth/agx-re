# EXP-M4-31: Apple9 binary-consumer candidate-route fields

This own-source Metal experiment asks whether the similarly placed three-bit
fields in native `falu2i`, `falu2`, and integer XOR instructions follow the
same scheduling rule seen in the earlier `ISELECT` probes.  The fields are
called `candidate_route` here rather than assuming that the current decoder's
larger `mods`, `mod_hi`, or `lut_b` labels imply their semantics.

The study is instruction-first.  MSL cases are only carriers.  A direct result
is admitted only when the extracted Apple9 stage main contains exactly one
source-qualified `falu2i`, `falu2`, or XOR target.  The analyzer tokenizes every
main and explicitly records the one four-byte atomic-return bridge whose field
semantics remain unknown.  Every case executes on T8132 in both forward and
reverse fresh-process order with a full 4-KiB output oracle.

The tested producers are system-derived ordinary GPR values and direct texture,
atomic-return, and threadgroup-return values.  Ordinary device-buffer loads are
intentionally excluded.  Each consumer has a last-use control, independent
uses of each available source, duplicate-result stores, and a downstream IMAD
consumer.  The analyzer determines what Metal actually scheduled rather than
trusting MSL statement order.  No candidate-route bits are mutated.

The generated corpus contains 56 semantic cases and 224 native source cases:
two equivalent formulations in precise and fast math modes.  See `RESULTS.md`
and `NATIVE_CENSUS.json` for the qualified result.

`captures/superseded-initial-forward` is retained as a supersession record.  It
contains the first pilot, whose buffer-derived ALU controls were optimized away
in several cases and whose atomic-float oracle had not yet modeled native
subnormal input flush.  The analyzer does not consume that directory.
