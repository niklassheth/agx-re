# EXP-M4-35: native load-to-XOR lowering

Small own-source Metal controls for determining how the Apple9 compiler moves
pending device-load returns into integer logic.  Each kernel is compiled in a
fresh process on T8132/macOS 26.6.2 (25G83), executed against a complete 4-KiB
oracle, and its serialized compute main is decoded.  Conclusions must follow
the emitted instruction and register flow, not MSL statement order.

The cases distinguish one loaded operand, two loads from separate buffers, two
loads from one buffer, and a two-consumer lifetime that also requires integer
addition.
