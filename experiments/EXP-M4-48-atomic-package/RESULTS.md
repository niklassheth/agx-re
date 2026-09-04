# EXP-M4-48: Apple9 atomic package contract

## Scope

This clean-room T8132/macOS 26.6.2 (25G83) capture uses the own-source Metal
workload in `harness/atomic8.m`. It deliberately binds eight buffers, performs
ordinary ALU and loads, executes a returning device atomic add, and writes a
four-word exact result record. The proprietary launch program is treated as an
opaque package input and is not disassembled.

## Package result

The captured carrier publishes its eight caller buffers directly at q0--q7.
Its relevant outer contract differs from the earlier non-atomic superset:

- archive call field at launch offset `0x70`;
- direct resource table with eight qwords and no three-resource hidden prefix;
- direct CDM words `0x00080000`, `0x01000000`, and `0x60010060`;
- one 64-byte constant program and one 1,024-byte opaque launch program.

The development inputs installed under `/home/nsheth/Projects/asahi/tmp/agx-apple9/carrier8-atomic`
are:

```text
9baa760c5185b9e5645bd1299e5ec948674258d6cbb0dc68b1394f1e45f3fd27  constant.bin
f712c5923161763e175403a715a66e4959239298e3905ce09d03bfe0e026d2ec  launch.bin
```

Replacing only the captured own-source stage main with Mesa's generated
Apple9 main passes exact target and result-buffer validation. The same main
under the ordinary superset launch contract leaves the atomic target
unchanged, establishing that the original compiler failure was a launcher ABI
mismatch rather than an atomic packet or scoreboard error.

## Mesa validation

The atomic carrier now selects by a semantic compiler profile, not by resource
count. Hardware validation through normal GLSL, Gallium, DRM UAPI, and the G16
shim covers:

- every integer operation selector, returned and discarded forms;
- compare-exchange success and failure;
- dynamic and affine addressing over multiple writable resources;
- sequential returned atomics with slot-6/r0 retirement;
- 256-lane contention with exact final memory and return permutation;
- divergent if/else and loop execution, including returned values;
- 32 consecutive dispatches into the same atomic counters;
- interleaved ordinary-superset, atomic, indirect ordinary, and loop programs
  in one process and persistent VM.

The capture does not establish indirect dispatch or the hidden
`gl_NumWorkGroups` resource tuple for this launcher. Mesa rejects those two
atomic-package combinations rather than conflating q0 with metadata.
