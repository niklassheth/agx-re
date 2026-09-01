# EXP-M4-27: native Apple9 vector SSBO semantics

This own-source experiment asks whether aligned Apple9 `uint2` and `uint4`
SSBO accesses use vector memory instructions, scalar component instructions,
or a mixture, and whether partial-component stores are implemented as masked
stores, scalar stores, or read-modify-write sequences.

The seven deliberately small cases are:

- `scalar_copy`: scalar package and instruction baseline.
- `uint2_copy` and `uint4_copy`: aligned whole-vector load/store comparisons.
- `uint2_alu` and `uint4_alu`: component-distinct arithmetic that prevents a
  vector copy from hiding component routing or lane-order mistakes.
- `uint2_store_x`: writes only `.x`, sourcing `.y`.
- `uint4_store_yw`: writes two non-contiguous components from different input
  components while `.x` and `.z` must retain `0xcccccccc`.

Every invocation uses a fresh process and runtime-compiles only its own MSL.
It checks the complete 4-KiB output image, including `0xcc` guard and untouched
components, and verifies the complete 4-KiB input is immutable. It writes the
pre/post input, pre/post output, and independent expected image into `raw/`.

## Capture preparation

Copy these source files to the macOS guest. Copy the canonical tracer source
from EXP-M4-26 into the same directory as `iotrace.c`; `build_guest.sh` fails
closed if it is missing. Then build:

```sh
./build_guest.sh
```

The later hardware operator should collect both orders as separate run IDs:

```sh
./run_guest_matrix.sh vector-forward forward
./run_guest_matrix.sh vector-reverse reverse
```

This directory only prepares the experiment. No target or capture is run as
part of its creation.

## Required analyzer contract

The later analyzer must fail closed unless every case has a zero status, the
`NATIVE_VECTOR_SSBO_OK` marker, identical 4-KiB pre/post input images, and a
post-output image byte-identical to `expected.bin`. It must independently
reconstruct the CPU oracle rather than trusting the captured expected file.

For each forward/reverse case it must extract and compare:

1. Exact main bytes, main length/hash, instruction boundaries, and the full
   device-load/device-store instruction census.
2. Load/store widths, offsets, register fields, and any per-component or write
   mask fields, without assigning semantics to unknown bits prematurely.
3. Resource-table bytes, constant/CDM blocks, launch allocation/call offset,
   state record, register count, and complete normalized package identity.
4. Pre/post memory differences. Whole-vector cases may change exactly
   `64 * width * 4` output bytes. Partial cases may change only the selected
   words; every untouched component and all trailing guard bytes must remain
   `0xcc`.
5. Exact agreement between forward and reverse runs for all normalized fields.

The decisive comparisons are scalar versus `uint2` versus `uint4` copy;
copy versus component-distinct ALU at the same width; and whole-vector versus
partial stores. A wider main is not by itself evidence of vector memory. The
instruction census and byte-level memory oracle must agree. An input load in a
partial-store main may indicate read-modify-write only if its address/resource
is demonstrably the output buffer rather than the ordinary input load.

The completed fail-closed audit is implemented in `analyze.py`; its concrete
package and ISA observations are recorded in `RESULTS.md`.
