# EXP-M4-52 results: Apple9 conditional nesting is an implicit stack

Native Metal does **not** encode conditional nesting depth in the predicate
destination or in the ordinary push/else/pop records.  The same canonical
records remain correct beyond the experimental Mesa compiler's depth-eight
boundary, through 32 simultaneously live conditional scopes on T8132.

This directly refutes the current Mesa hypothesis that successive ordinary
conditionals require predicate destinations `p0, p2, p4, ...` and push
selectors `1, 5, 9, ...`.  Those progressions are not the native conditional
stack model.

## Native results

The generated own-source kernels were compiled at depths 1 through 12, 16, 24,
and 32.  Every level had observable writes in both arms, and every true arm had
another observable write after its child returned.  One lane followed the
all-true path through the complete tree, while the other lanes exited at
different levels.  Thus no tested level was statically or dynamically dead.

| Depth | Main bytes | Pushes | Else-mask ops | Pops | Maximum live pushes | Hardware |
|---:|---:|---:|---:|---:|---:|---|
| 1 | 296 | 1 | 1 | 1 | 1 | 2/2 exact |
| 4 | 964 | 4 | 4 | 4 | 4 | 2/2 exact |
| 8 | 1,940 | 8 | 8 | 8 | 8 | 2/2 exact |
| 9 | 2,200 | 9 | 9 | 9 | 9 | 2/2 exact |
| 12 | 3,012 | 12 | 12 | 12 | 12 | 2/2 exact |
| 16 | 4,054 | 16 | 16 | 16 | 16 | 2/2 exact |
| 24 | 6,188 | 24 | 24 | 24 | 24 | 2/2 exact |
| 32 | 8,256 | 32 | 32 | 32 | 32 | 2/2 exact |

All 15 kernels compiled successfully in fresh processes in both forward and
reverse order.  Their extracted `_agc.main` bytes were identical across the
two orders.  All 30 hardware executions reported `STATUS OK` and matched all
1,088 output words, including poison retained in every unvisited trace cell.

The native conditional sequence at every level was:

```text
predicate compare to the current predicate
0f 05 54 01                 push and narrow
0f 01 54 <signed target>    skip empty arm
...
0f 04 04 19                 select the other arm
0f 01 54 <signed target>    skip empty arm
...
0f 06 04 01 00 00           pop and reconverge
```

The push bytes were exactly `0f 05 54 01` at all 150 levels in each compile
order (300 extracted instances total).  The
else-mask bytes were exactly `0f 04 04 19`, and every pop was exactly
`0f 06 04 01 00 00`.  Only branch displacements varied.  The raw structural
scan found exactly `D` balanced pushes and pops, with a maximum of `D` pushes
live at once for every depth `D`; depth 32 was not flattened into a shallower
machine tree.

The compare immediately preceding every push used normalized predicate
destination zero.  The last depth-32 sign-bit test used byte-0 inversion form
`0x1a` rather than `0x0a`; after separating the independently known inversion
bit, its destination is still zero.  Predicate registers therefore do not hold
the enclosing mask stack.  The push consumes the current predicate, while the
mask machine saves the enclosing execution state internally.

## Boundary conclusions

- There is no eight-level conditional nesting limit.  Hardware correctness is
  established through 32 live scopes; this experiment does not claim that 32
  is the architectural maximum.
- Crossing depths 8, 16, and 24 introduces no new mask-control opcode, form,
  bank, or explicit pop/spill/reset.
- Ordinary `if` lowering should reuse the canonical predicate destination and
  canonical push/else/pop encodings at every nesting level.
- Compiler nesting depth is still useful for validating balanced structure and
  resolving CFG edges, but it must not be encoded into ordinary conditional
  predicate or mask fields.
- Loop latch updates, nonlocal break/continue unwind records, and call frames
  have additional controls.  This experiment does not erase those distinct
  semantics or prove that their fields are depth-free.

The Apple9 descriptor database cannot currently tokenize the complete
depth-five-and-higher programs because register pressure selects unrelated
high-register ALU/move forms that remain undescribed.  This does not affect the
mask result: mask records have complete, exact leaders; the experiment retains
the full main bytes; the structural scan is parcel-aligned; each program has
exactly balanced counts and nesting; and every complete program was executed
with an exact oracle.  The decoder gaps are reported in
`raw/native_analysis.json` rather than silently repaired.

## Mesa implication

The current depth-eight rejection is self-inflicted.  For ordinary
conditionals, remove the depth-derived `2 * mask_depth` predicate destination
and `1 + 4 * depth` push selector.  Emit the native constant forms and retain
only a software stack of CFG scopes.  Before applying the same simplification
to loop-update or nonlocal-unwind fields, run equivalent mixed/deep loop probes;
those operations encode more than an ordinary conditional push/pop.

## Artifacts

- `generate.py` and `deep_mask_stack.metal`: generated own-source corpus.
- `run_native.py`: fresh-process compilation, execution, and CPU oracle.
- `analyze_native.py`: stage-main extraction and mask-stack census.
- `raw/native_results.json`: complete diagnostics and exact output words.
- `raw/native_analysis.json`: complete stage-main hex, compile-order comparison,
  mask records, and decoder-gap disclosure.
- `raw/hex/`: extracted own-source `_agc.main` hex streams.

Environment: Apple M4/T8132, macOS 26.6.2 build 25G83.  Generated source SHA-256:
`e15c3109163f2b06785ce64858bf1a5ca664896d1cf507d9fd1359d726642bc0`.
