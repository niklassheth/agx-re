# EXP-M4-33: Apple9 route handoff

This is a bounded native-Metal follow-up to EXP-M4-30/31.  It tests whether
the apparent "prior read changes the next route" effect is already encoded by
the prior reader.

Each qualified program contains two asynchronous float returns, followed by:

1. a route-bearing `falu2i` that reads one return and keeps it live; and
2. a route-bearing binary `falu2` that rereads that return while combining the
   two original returns.

The corpus varies only the return read first and the producer issue order.  A
two-producer chain arm also makes three retained reads of the same return
before the final binary read, to expose the route sequence without a broad
field sweep.
The analyzer records the complete bytes and decoded lifetime/publication state
of both consumers.  MSL statement order is not evidence: a case is retained
only when the decoded instructions have the intended order and dataflow.

Ordinary device-buffer loads are intentionally absent.  No instruction bits
are mutated in this native phase.

## Reproduction

On the host:

```sh
python3 generate.py
```

On the T8132 macOS environment, with this experiment, EXP-M4-29, and the
canonical ISA tools staged together:

```sh
./build_guest.sh
python3 run_native.py native-forward forward
python3 run_native.py native-reverse reverse
```

Copy the captures back and run:

```sh
python3 analyze_native.py
```

The bounded IMAD cross is generated after the native corpus with:

```sh
python3 splice_imad_cross.py
```

After executing those four archives twice with the native runner, reproduce
its machine-readable verdict with `python3 analyze_imad_cross.py`.
