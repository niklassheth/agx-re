# EXP-M4-40: compute carrier parameterization

This own-source T8132 experiment isolates launch/package parameters that might
otherwise force Mesa to retain several opaque compute carriers.

- `t8132_tgmem_parameter_matrix.m` is the Metal workload and exact oracle.
- `stage_and_run_tgmem_matrix.py` stages it into the macOS guest.
- `raw/tgmem-param-01/` contains the captured caller package and guest result.
- `analyze_parameter_matrix.py` checks the byte-level structural invariants
  without decoding proprietary launch or archive code.
- `RESULTS.md` records the indirect, shared-memory, and occupancy conclusions.
