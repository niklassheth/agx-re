# EXP-M4-41: Apple9 reciprocal scheduling fields

This experiment identifies the accurate Apple9 reciprocal instruction and
separates its arithmetic encoding from source retain/release and scoreboard
handoff state.

The initial census walks `_agc.main` programs from the public-source Metal
corpus captured by EXP-M4-32. It does not inspect the opaque launch program,
constant program, or any proprietary Apple binary.

```sh
python3 experiments/EXP-M4-41-reciprocal-slots/analyze_corpus.py
```

Focused own-source native variants and hardware mutations will be added for
relationships the corpus cannot settle by itself.

The completed decode, exact T8132 ablations, and reciprocal-accuracy result
are in [RESULTS.md](RESULTS.md). `HARDWARE_RESULTS.json` is the compact
machine-readable result ledger; `captures/native-v1/` contains only archives
compiled from `kernels/reciprocal_slots.metal`.
