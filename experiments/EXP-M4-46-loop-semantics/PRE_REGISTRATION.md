# EXP-M4-46: Apple9 loop semantics pre-registration

All inspected shaders are own-source MSL.  This experiment inspects only the
resulting `_agc.main` regions and executes them through public Metal APIs.  It
does not inspect Apple framework binaries, launch helpers, or other proprietary
programs.

## Questions

1. Is the `0f 00` signed displacement based at the instruction start, `PC+4`,
   or the instruction end?
2. Is the ordinary loop backedge taken exactly while the current execution
   mask contains an active lane?
3. Which push/pop forms delimit loop entry, loop iterations, and ordinary
   nested divergence?
4. How does native Metal encode per-lane loop exit, `break`, `continue`, nested
   loops, and loops entered beneath an existing divergent mask?
5. Does native Metal keep pending asynchronous results across a backedge, or
   materialize/fence them before the control-flow boundary?

## Acceptance criteria

- Every native kernel must match all 64 output words against an independent CPU
  oracle for lanes with zero, one, and many iterations.
- A branch-target convention is promoted only when it uniquely lands on decoded
  instruction boundaries across the corpus and all fresh captures.
- Mask-stack fields are described structurally unless a focused hardware test
  establishes their exact semantics.
- Any encoding ablation must begin from a passing native control, target an
  instruction boundary, use a per-case watchdog, and stop after two hangs.
- No Mesa compiler changes are part of this experiment.
