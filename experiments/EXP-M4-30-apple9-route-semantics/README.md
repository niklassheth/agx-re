# EXP-M4-30: Apple9 route semantics

This is a bounded, compute-only experiment for the recurring three-bit route
field in basic Apple9 ALU consumers.  It assumes common field semantics across
instruction families until controlled native evidence demonstrates otherwise.

The native Metal compiler supplies every instruction stream.  The current
phase is deliberately native-only: no route bits have been altered.  Every
execution compares the complete 4-KiB output buffer.

## Native panels

The initial ALU panel applies XOR/add transformations before ISELECT.  Assembly
review found that Metal sometimes factors those operations after the select,
creating a direct device-load edge; those cases are classified from their
instructions rather than their source labels.

The initial consumers are compact float add/multiply, float FMA, float select,
and integer select.  The producer shapes are ordinary float/integer ALU
results, materialized predicates, and ALU-transformed system indices.  Cases
vary operand live-after roles and bounded source-level separation pressure.
Two controlled integer-select panels then isolate selected-arm expression
shape, destination fanout/consumer shape, and load-derived versus system-only
producer chains.

The follow-up direct-return panel authors four texture, atomic, or threadgroup
returns feeding ISELECT.  It varies which return is also consumed by an IMAD,
whether that result is merged or stored independently, compare spelling,
texture-coordinate assignment, and output fanout.  The analyzer requires the
intended ISELECT/IMAD instruction graph, exact output, formulation stability,
and compilation-order stability before promoting a route observation.
Ordered atomic and barrier-separated threadgroup variants swap the first two
return instructions to distinguish semantic tuple position from the physical
return slot selected by the scheduler.

A final matched atomic-return 2x2 crosses selected-arm form with prior-return
reuse.  The first axis feeds ISELECT either the raw p2/p3 returns or two
distinct single-IMAD materializations.  The second axis puts a reuse IMAD of
the first- or second-issued return immediately before ISELECT.  The analyzer
rejects the panel unless all four ISELECTs are identical outside the route
field and the intended post-return instruction sequence is present.

## Reproduction

On the host:

```sh
python3 generate.py
```

Copy this directory, its `EXP-M4-29-apple9-provenance-matrix` sibling, and the
canonical `tools/agx-isa` and `tools/shdump` directories to the T8132 macOS
environment.  There:

```sh
./build_guest.sh
python3 run_native.py native-all-forward forward
python3 run_native.py native-all-reverse reverse
```

Native archives must be mechanically censused before any ablation is emitted.
An archive is excluded if the intended consumer family or route-bearing form
cannot be identified unambiguously.

Copy the two capture roots back to this directory.  On the host, run
`python3 analyze_native.py` to reproduce `NATIVE_CENSUS.json`.  The checked-in
evidence was collected in smaller historical batches, which the analyzer also
accepts.  The interpreted native-only findings and their limits are in
`RESULTS.md`.
