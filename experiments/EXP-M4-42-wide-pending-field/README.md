# EXP-M4-42: Apple9 wide-instruction pending field

This clean-room experiment investigates instruction bits 12--17 in Apple9
operand-bearing integer, conversion, bitfield, and special-function forms.
Every native program is compiled from the MSL under `kernels/`; no proprietary
Apple program is inspected.

The initial corpus hypothesis is that the six bits correlate with pending
producer slots 1--6.  The experiment distinguishes three possibilities:

1. a required six-bit dependency mask;
2. an optional forwarding/scheduling hint associated with those slots; or
3. unrelated per-family fields which merely correlate in the observed corpus.

Native controls and mutations are compared by complete output, and every run
uses a per-case timeout.
