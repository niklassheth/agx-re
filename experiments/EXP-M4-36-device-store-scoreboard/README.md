# EXP-M4-36: direct device-store scoreboard selection

This own-source T8132 experiment asks how the Apple9 `device_store` form with
byte 1 `0x56` consumes a pending scalar `device_load` result.

The decisive programs hold two distinguishable loads pending simultaneously.
The loads publish into distinct scoreboard slots and destination GPRs.  Two
stores then reverse their byte-3 source selectors, while producer issue order
and producer slot tags are varied independently.  Full five-word output is
read back; word 4 is an ordinary-ALU-path execution canary.

The hypotheses are:

- **GPR-associated scoreboard lookup:** each store obtains the pending value
  associated with the half-register named by store byte 3.
- **Implicit slot 6:** the direct store always consumes slot 6, regardless of
  byte 3.
- **Issue-order queue:** the direct store consumes newest/oldest pending work,
  regardless of byte 3.
- **Hidden selector:** neither producer slot nor byte 3 explains the result.

Generate locally with `python3 generate.py`.  On the pinned T8132 macOS host,
build `tools/agxtest/shdump` and `tools/agxtest/agxrun`, then execute
`python3 run.py RUN_ID`.  Each arm runs in a fresh process with a watchdog and
three complete-output repetitions.

The completed result is in [RESULTS.md](RESULTS.md): byte 3 associates the
store with a pending value's GPR, but the conservative compiler rule admits
direct forwarding only from slot 6, matching every high-confidence native
pair in the corpus.
