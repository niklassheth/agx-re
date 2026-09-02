# EXP-M4-37: Apple9 mode-3 literal form

This is an own-source Metal experiment for separating the eight-byte scalar
`MOV_IMM32` form (mode 2) from the pending tuple-publication form selected by
mode 3. It inspects and mutates only shaders compiled from the sources under
`kernels/`.

The experiment started with these questions:

1. Is `40 xx` consumed as part of the mode-3 instruction?
2. Which byte-2 bits extend the scalar literal destination, and which are
   independent modifiers?
3. Is the scalar destination six or seven bits wide?
4. Can mode 2 replace mode 3 when no constrained texture/output route is
   required?

The scalar investigation resolved byte-2 bits 7:6 as destination bits 5:4,
making a six-bit r0..r63 destination. Byte-2 bit 4 is native-zero and bit 5 is
an independent native modifier whose unrestricted semantics remain unknown.
The completed scalar encoding, the bounded mode-3 model, and exact hardware
results are recorded in `RESULTS.md`.
