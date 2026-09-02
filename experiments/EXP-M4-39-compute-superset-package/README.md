# EXP-M4-39: Apple9 compute superset package

This is a clean-room, own-source Metal experiment for replacing Mesa's
resource-count-selected Apple9 compute wrappers with one eight-buffer superset
carrier.

The executable programs emitted by Metal are treated as opaque.  The
experiment observes only caller-visible package layout, resource addresses,
dispatch dimensions, and exact output.  It does not disassemble or decompile
the constant, launch, helper, or main programs.

The first candidate ABI has eight visible buffers: seven independently
distinguishable read-only inputs and one output.  Its shader also consumes the
complete direct-dispatch geometry so the same carrier can be tested in 1D, 2D,
and 3D.  Every buffer has prefix and suffix guards and every output word has an
independent CPU oracle.

## Native harness

Build on macOS:

```sh
clang -fobjc-arc -O2 -framework Metal -framework Foundation \
  -o carrier8 harness/carrier8.m
```

Representative cases used for the normalized carrier and geometry controls:

```sh
./carrier8 --grid 64 1 1 --local 16 1 1
./carrier8 --grid 9 7 1 --local 4 2 1
./carrier8 --grid 5 4 3 --local 2 2 1
./carrier8 --grid 64 1 1 --local 16 1 1 --offset-step 64
```

The T8132 compute-sequence tracer captures the fixed USC archive and the
launch, state, resource, CDM, and argument mappings structurally:

```sh
G16G_COMPUTE_SEQUENCE_CAPTURE_DIR=/path/to/raw \
G16G_COMPUTE_SEQUENCE_CAPTURE_PACKAGE=1 \
G16G_COMPUTE_SEQUENCE_RESOURCE_COUNT=16 \
  proxyclient/tools/run_guest.py \
    -m proxyclient/hv/trace_t8132_compute_sequence.py ...
```

`RESULTS.md` will distinguish native observations, successful reconstructed
controls, and unresolved fields. `harness/extract_carrier.py` reduces one
control capture into a normalized manifest and external development files. It
also extracts only the proven 8-KiB helper table from the larger captured
allocation page.

The normalized binary inputs live outside Git at:

```text
/home/nsheth/Projects/asahi/tmp/agx-apple9/carrier8
```
