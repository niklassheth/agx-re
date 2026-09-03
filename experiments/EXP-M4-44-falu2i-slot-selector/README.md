# EXP-M4-44: FALU2I pending-slot selector cross

This clean-room experiment tests whether Apple9 `falu2i` instruction bits
45--47 are a three-bit pending-result slot selector.

The native input is one own-source Metal compute kernel containing an adjacent
device load, `falu2i` addition by 1.5, and device store.  The experiment
retags the device-load producer to each slot 1--6 and independently sets the
consumer field to every value 0--7.  Register selection, arithmetic, package,
buffers, and all other instruction bits remain fixed.

For each producer slot, the predicted result is that only the numerically
matching consumer selector exposes the pending value.  Selector zero is the
ordinary/materialized-GPR control; selector seven checks the unused encoding.
Every case compares the complete four-word output against an independently
computed bit-exact oracle and is repeated in a second pass with reversed case
order.
