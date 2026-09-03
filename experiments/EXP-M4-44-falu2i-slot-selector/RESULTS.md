# EXP-M4-44 results: FALU2I bits 45--47 are a slot index

## Result

For pending slots **1--6**, Apple9 `falu2i` instruction bits **45--47** are a
three-bit numeric slot selector:

```text
consumer bits 45--47 == producer slot  -> loaded value is consumed
consumer bits 45--47 != producer slot  -> stale zero GPR value is consumed
consumer value 0                        -> ordinary/materialized GPR path
```

This is now hardware-validated across the complete slot-1-through-slot-6
product.  The experiment does not merely rely on Metal's allocation
correlation.

Selector 7 is intentionally outside this closure.  It aliases slots 1 and 2
in this carrier and does not expose slots 3--6.  This is recorded exactly but
not interpreted here.

## Exact experiment

The own-source kernel contains one adjacent sequence:

```text
0x00  get_sr
0x04  device_load
0x12  falu2i       # load result + 1.5
0x18  device_store
0x26  stop
```

The native main is 42 bytes.  Metal assigns the load to slot 6 and emits
`falu2i` selector 6.  Its unmodified output is bit-exact for four
distinguishable inputs:

| Input | Expected result |
|---:|---:|
| `1.0` | `2.5` |
| `-2.0` | `-0.5` |
| `3.25` | `4.75` |
| `100.0` | `101.5` |

The device-load producer token at instruction bytes `+8/+9` was retagged to
each independently established slot encoding:

| Slot | Producer token bytes |
|---:|---:|
| 1 | `11 00` |
| 2 | `51 00` |
| 3 | `91 00` |
| 4 | `d1 00` |
| 5 | `11 01` |
| 6 | `51 01` |

For each producer slot, the consumer's bits 45--47 were swept through values
0--7.  All other producer and consumer bytes, registers, package state,
buffers, and dispatch parameters remained fixed.  The entire matrix was run
in forward and reverse order, then the complete 96-execution experiment was
repeated independently.  Every case used a fresh `agxrun` process and a
15-second watchdog.  The two runs produced identical forward-order signatures
and identical reverse-order signatures.

## Hardware observations

For the closed selector domain 0--6:

| Relationship | Exact outputs | Total |
|---|---:|---:|
| Matching producer slot and selector | **24** | **24** |
| Mismatched producer slot and selector | **0** | **144** |

Every command returned `STATUS OK`; there were no command-buffer faults or
hangs.  Each matching case returned the complete four-word oracle.  Every
mismatched 0--6 case returned `1.5` in all four lanes: the immediate operand
alone.  Thus a mismatched selector makes `falu2i` read a zero/stale ordinary
GPR value; it does not corrupt the arithmetic or silently skip the command.

Selector 7 was stable across both orderings and both complete repetitions
(**8/24** exact overall):

| Producer slot | Selector-7 result |
|---:|---|
| 1 | exact |
| 2 | exact |
| 3 | immediate-only |
| 4 | immediate-only |
| 5 | immediate-only |
| 6 | immediate-only |

That behavior proves selector 7 is not simply an invalid encoding, but its
meaning is deferred.

## Same-boot producer-token control

A separate own-source `device_load -> u2f` kernel repeated the established
wide-consumer cross on the same boot and with the same tools:

- matching producer tag and one-hot consumer mask: **6/6 exact**;
- neighboring one-hot mask: **0/6 exact**.

This rules out stale tools, a changed boot, or nonfunctional producer-token
mutations as explanations for the `falu2i` result.

## Native allocation corroboration

A second own-source kernel keeps six independent device loads pending.  Metal
emits six `falu2i` consumers with high-three-bit values:

```text
6, 1, 2, 3, 4, 5
```

The unmodified kernel executes exactly.  Broad route mutations in this longer
schedule are timing-sensitive because several load results become durable
before consumption, so those mutations are retained as corroborating native
evidence rather than used for the functional proof above.

## Invalid pilot retained

`INVALID_wrong_token_offset_run01.json` is not ISA evidence.  The pilot
mistakenly modified device-load bytes `+12/+13` instead of the producer token
at `+8/+9`; every load consequently produced zero.  The offset error was found
by comparing the actual splice log to the independent EXP-M4-42 control before
interpreting the result.  The file is retained so the correction is auditable.

## Consequence

The basic `falu2i` field is no longer merely inferred from its alignment with
`falu2`.  For slots 1--6, it is independently proven to be the same numeric
pending-result slot selector.  Compact FALU's three-bit encoding can therefore
be understood as a compressed selector for the same six-slot mechanism whose
wider consumers expose as a six-bit one-hot dependency mask.

The two complete matrix records are in `RAW_m4-20260903-run02.json` and
`RAW_m4-20260903-run03.json`.  The supporting controls are in
`NATIVE_SELECTOR_RESULTS.json`, `WIDE_CONTROL_RESULTS.json`, and
`NATIVE_SIX_RESULTS.json`.
