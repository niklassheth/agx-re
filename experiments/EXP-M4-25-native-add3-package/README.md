# EXP-M4-25: native T8132 three-buffer compute package

This experiment captures the complete caller-owned Metal package for the
own-source kernel `out[i] = a[i] + b[i]` on T8132.  It uses only public Metal
APIs and data tracing at the IOKit boundary.

The harness emits two full BO/map snapshots:

- `dump00`: after encoding and before command-buffer commit.
- `dump01`: after the command buffer reports completion.

Inputs, the poisoned output preimage, exact expected output bits, and all three
postimages are retained separately under `raw/`.  The output has 64 lanes, a
32-thread local size, and a 768-byte untouched guard region.

On the macOS guest:

```sh
sh build_guest.sh
sh run_guest_capture.sh capture-native-add3
```

The pinned tracer is `tmp/agx-re/tools/iotrace/iotrace.c`, SHA-256
`66d8f3a38588ca8e3c81b22cd987690a5441955fe3ac80be0a193acbf5e312f3`.
Required tracer limits are 1 MiB per BO/map and 64 KiB per IOKit structure,
with per-signal directories enabled as shown in the run script.

Verify the canonical capture and its independent repeat with:

```sh
python3 analyze.py
```

See `RESULTS.md` for the packaging audit and its Mesa implications.
