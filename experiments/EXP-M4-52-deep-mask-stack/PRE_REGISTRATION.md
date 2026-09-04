# EXP-M4-52: deep Apple9 execution-mask nesting

This clean-room experiment compiles and executes only our own MSL kernels.  It
extracts only their `_agc.main` stage programs.  It does not inspect Metal
framework binaries, launch helpers, or any other proprietary program.

## Question

The current experimental Apple9 compiler models a single four-bit progression
of mask selectors and therefore rejects more than eight simultaneously active
structured scopes.  What does native Metal emit for genuinely divergent,
observable source nesting at and beyond that apparent boundary?

The alternatives to distinguish are:

1. another instruction field or mask-stack bank extends the same scheme;
2. Metal spills or otherwise frames mask state around the boundary;
3. Metal restructures deep source control flow into shallower machine control
   flow;
4. pipeline compilation rejects the program.

## Probe design

- Compile depths 1 through 12, plus 16, 24, and 32, in fresh processes.
- Repeat compilation in reverse order to detect cache/order artifacts.
- Load one runtime path bit-mask per lane.  The lane patterns include an
  all-true path, an all-false path, alternating paths, and exits at boundaries
  around levels 8 and 9.
- At every level, both arms write distinguishable values.  The true arm writes
  both before and after its nested child.  This prevents a source-level nested
  scope from becoming semantically dead or tail-only.
- Seed the complete output buffer with nonzero poison and compare every word,
  including locations belonging to unvisited inner levels.

## Acceptance criteria

- A claimed native high-depth mechanism must be present in both compile orders.
- The analyzer must report decoded instruction offsets and raw bytes around all
  mask-control records; unknown records are retained rather than guessed.
- Each successfully compiled kernel must execute on T8132 and match the full
  independent CPU oracle on at least two fresh runs.
- Compilation success by itself is not evidence that the emitted machine
  control flow is correct.
