# EXP-M4-16 — Apple9 operand-encoding matrix

This experiment turns caller-owned Apple9 compiler output into an
allocator-facing contract. It keeps three evidence levels separate:

1. a field is correlated in caller-owned compiler output;
2. changing it has an observed hardware result;
3. every register/class/cache bit needed by a packer is understood.

Only level 3 is marked allocator-safe. A descriptor byte that resembles
`(register << 1) | size` is not enough: its high bit may be a cache, liveness,
or source-file selector rather than another register-index bit.

## Capturing compiler output

The generated `.metal` files contain only our own kernels. macOS is launched
exclusively through the repository's hypervisor `run_guest.py` route; there is
no direct macOS launch path for this target. Inside that guest, the public
Metal API compiles the generated sources and the existing caller-owned shader
tools save each `_agc.main` stream. Generated Metal sources and binary output
live under ignored `work/`.

The generator families deliberately stress different allocation cases:

- `generate_pressure_msl.py`: 16/32/64/96 live-value pressure;
- `generate_float_ring_msl.py`: independently varying float operands;
- `generate_noncoalesced_msl.py`: destination cannot coalesce with source A;
- `generate_probes.py`: short source-side programs for one-field hardware A/Bs.

## Offline checks

```sh
python3 analyze_operand_matrix.py
python3 analyze_fma_pressure.py work/pf16.main work/pf32.main \
  work/pf64.main work/pf96.main
python3 generate_probes.py generated
python3 ../../tools/agx-isa/roundtrip_test.py
```

## Hardware probes

These probes execute after chainloading m1n1; they do not launch macOS. Every
run needs a fresh reset because the focused source compute runner powers SGX
down on exit.

```sh
uv run --with-requirements /home/nsheth/Projects/asahi/m1n1-m4-agx/requirements.txt \
  python /home/nsheth/Projects/asahi/m1n1-m4-agx/proxyclient/experiments/agx_g16g_compute.py \
  --workload hand-assembled-constant-u32 \
  --apple9-main generated/iadd-roundtrip-r64.bin \
  --apple9-program constant --apple9-expected-u32 1
```

The current exact results and the negative float controls are recorded in
`RESULTS.md`.
