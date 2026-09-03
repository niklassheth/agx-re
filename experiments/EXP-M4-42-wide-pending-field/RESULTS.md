# EXP-M4-42 results: the wide pending-slot field

## Result

Instruction bits **12--17** form a six-bit scoreboard dependency mask in the
tested Apple9 wide consumer forms.  The byte geometry is:

| Pending slot | Instruction bit | Encoding contribution |
|---:|---:|---:|
| 1 | 12 | `byte[1] |= 0x10` |
| 2 | 13 | `byte[1] |= 0x20` |
| 3 | 14 | `byte[1] |= 0x40` |
| 4 | 15 | `byte[1] |= 0x80` |
| 5 | 16 | `byte[2] |= 0x01` |
| 6 | 17 | `byte[2] |= 0x02` |

Thus the familiar byte-2 values are not independent modes:

```text
0x54 = no pending-slot dependency
0x55 = wait for slot 5
0x56 = wait for slot 6
0x57 = wait for slots 5 and 6
```

The complete mask is:

```c
pending_mask = (byte[1] >> 4) | ((byte[2] & 3) << 4);
```

This is a real mask, not a binary slot number.  Multi-bit values execute, and
adding an unrelated bit to a correct one-hot dependency preserves exact output.

## Hardware evidence

All tests ran on T8132/macOS 26.6.2 build 25G83 using only own-source Metal
programs.  Every comparison covers the complete four-lane output buffer.

### Single pending producer

For each of these direct slot-6 cases, masks containing bit 5 were exact and
masks lacking bit 5 read the old zero GPR value:

- signed and unsigned integer-to-float conversion;
- float-to-unsigned conversion;
- accurate reciprocal;
- popcount and count-leading-zeros;
- immediate bit extract/right shift;
- three-source integer multiply-add; and
- `extract_bits`.

The sampled masks were `00,01,02,04,08,10,20,21,30,3f`.  For all nine
families, exactly `20,21,30,3f` succeeded.  The bad reciprocal cases returned
positive infinity, which is `1/0`; the other unary consumers returned zero.
This distinguishes a stale ordinary GPR read from a retired or malformed Work
item.

### Complete producer/consumer cross

The device-load producer token was then retagged to each slot 1--6 and crossed
with the consumer mask in seven independently encoded families:

- `u2f`;
- reciprocal;
- popcount;
- bit extract;
- IMAD with three load inputs in one pending group;
- integer add; and
- integer subtract.

Across **126 executions**:

- matching one-hot bit: 42/42 exact;
- neighboring one-hot bit: 0/42 exact;
- matching plus neighboring bit: 42/42 exact.

This both establishes all six bit positions and shows that the mapping is
shared by several instruction families.  It supersedes the old description of
`0x54/0x56` as a generic boolean “handoff disabled/enabled” switch.

### Two distinct pending slots

Two adjacent loads were assigned different slots and consumed by one integer
add.  Four slot pairs were tested: `6+1`, `1+6`, `2+5`, and `3+4`.

- Mask zero failed in 4/4 schedules.
- The mask containing both slots was exact in 4/4 schedules.
- A mask containing only one slot sometimes exposed only one input and
  sometimes happened to be exact.

For example, with slots `6+1`, waiting only for slot 1 produced exactly the
second input, while waiting for both produced the sum.  Which one-bit arm was
already sufficient changed with schedule and inputs.  This is the expected
signature of a **wait/dependency mask**: after the selected completion event,
the instruction reads its normal GPR operands.  An unselected result can still
be correct if it has already become durable, but that is a timing accident and
not a compiler rule.

This also explains why native Metal normally assigns multiple loads feeding one
IMAD or IADD to the same pending slot: one scoreboard event covers the group.
When an instruction truly depends on independently allocated groups, the safe
encoding is the union of their live slot bits.

## Why some mutations looked inert

The own-source `dec_iso_absmulti` program is a particularly clean native
witness: its consumers walk masks `20,01,02,04,08,10`, exactly matching Metal's
six-slot load allocation.  Nevertheless, replacing any one mask—or sweeping all
64 values on the first consumer—left its final output unchanged.  Its loads are
hoisted far ahead of those consumers, so their GPR values have already become
durable.  The ordinary path therefore succeeds even with a wrong wait mask.

This is why a useful mutation must keep the producer adjacent enough that a
wrong mask actually observes stale data.  Corpus correlation alone identifies
the field; the direct hardware crosses establish its functional meaning.

## GET_SR correction

Metal does correlate GET_SR's byte-3 high bits with this consumer mask.  In the
own-source `sys_three` case, three GET_SR instructions end in `06,26,46`, and
the following direct conversions use mask bits 0 and 1.  Similar sequences are
common in the corpus.

However, that correlation does **not** make GET_SR a proven asynchronous
scoreboard producer:

- all 36 producer-suffix/one-hot-consumer combinations were exact;
- all six producer suffixes with a zero consumer mask were also exact; and
- clearing both native conversion masks in a three-GET_SR program preserved the
  complete 12-word output.

The best current model is that Metal carries the same generic
publication/dependency bookkeeping across GET_SR values, while GET_SR itself is
available on the ordinary GPR path before its immediate tested consumers.  Its
suffix may still describe cache/publication allocation used under pressure, but
the low-pressure hardware evidence does not establish a required producer-slot
contract.  Calling the byte-1 high nibble “GET_SR publication state” was
therefore too strong: it is the low four bits of the consumer's pending-slot
mask.

## Scope across instruction families

The same bits-12--17 geometry is now hardware-proven for direct pending loads in
IADD/ISUB, IMAD, integer/float conversions, reciprocal, bit-count, and bitfield
forms.  The own-source 1,080-program census additionally observes one-hot values
through slots 1--6 in `iadd2`, `ibfe`, and `ishift`, and nonzero values in
`ibfins`, `fspecial`, and the conversion forms.

This does not mean every Apple9 instruction stores its dependency mask there.
Known counterexamples use other envelope-specific locations:

- extended integer logic has a six-bit mask split across bits 45--47 and
  61--63;
- basic FALU/FALU2 forms use their established route/slot field; and
- compact forms may have an implicit or differently placed dependency.

The shared concept is the pending-slot dependency, not one universal physical
bit position across all encodings.

## Decoder and compiler consequences

The following current labels are now known to overlap one shared field:

- `fspecial.src_ext` plus the low bits of `fspecial.src_cache`;
- `iadd2.srcB_reg_hi`, `b2_bit0`, and `store_en`;
- analogous byte-1-high/byte-2-low fields in IMAD, conversion, shift,
  bit-count, and bitfield descriptors.

They should become one `pending_mask` operand in each applicable encoding.
In particular, `0x56` means slot-6 dependency, not a backwards-compatible
pending-source mode.

The conversion decoder also matches too much of byte 1.  Native forms such as
`a7 27 54 ...` and `a7 47 54 ...` are ordinary conversions with slot-2 and
slot-3 dependencies, but the current length logic can misclassify them as
longer shift forms.  Its opcode match must ignore byte 1's high nibble after the
shared field is represented.

Source last-use/release controls remain separate.  Waiting for a pending slot
does not imply releasing either the slot's GPR value or any source register.

Machine-readable results and exact logs are in `HARDWARE_RESULTS.json`,
`CROSS_RESULTS.json`, `MIXED_RESULTS.json`, and `ANALYSIS.json`.
