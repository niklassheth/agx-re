# EXP-M4-34: Apple9 route allocator closure

Own-source native-Metal cases for texture initial allocation, scalar device-load
allocation and gap reuse, retained-value materialization, and binary/ternary
consumption of multiple pending results.

The generated MSL is only a request.  A case contributes semantic evidence only
after the analyzer verifies the emitted instruction order and operand flow.
Every accepted native archive is executed on T8132 and checked against the
complete 4-KiB output oracle.

Run `generate.py` to regenerate the 50 own-source cases and their independent
oracles.  `run_native.py` executes fresh native compilations.  The two
`prepare_*_ablations.py` scripts make bounded field-only mutations of reviewed
own-source archives, and `run_route_ablations.py` executes those archives with
exact readback.  `analyze.py` is the closure gate and writes `RESULTS.json`.

The concluded compiler-facing model and its limitations are in `RESULTS.md`.
