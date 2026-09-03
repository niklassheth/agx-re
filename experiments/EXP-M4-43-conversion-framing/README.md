# EXP-M4-43: Apple9 conversion framing

This clean-room experiment tests whether the apparent trailing `02 00` or
`03 00` bytes of the Apple9 float-to-integer conversion are part of a ten-byte
instruction or a separate two-byte instruction.

The carrier is an own-source Metal compute shader.  At the disputed boundary,
the experiment replaces the native bytes with independently established
two-byte `mov_imm` instructions that write several distinguishable constants
to the conversion destination.  If the conversion is eight bytes and the
suffix is a separate instruction, those constants must overwrite the converted
value before the following store.  If the conversion consumes ten bytes, the
same bytes are conversion continuation fields and the compact moves do not
execute.

No proprietary Apple binary is inspected.
