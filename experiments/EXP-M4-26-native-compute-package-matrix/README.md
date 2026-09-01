# EXP-M4-26: native T8132 compute-package matrix

This clean-room experiment compares complete caller-owned Metal packages for
fresh-process compute pipelines with one, two, three, and four buffers.  It
also compares a copy and four scalar transforms with the same two-buffer
interface, plus distinct arithmetic DAGs with the same three-buffer interface.
The purpose is to determine which archive constant, launch, state, and resource
bytes are properties of the resource interface and which vary with the
authored main program.

Every case uses public Metal APIs and an own-source runtime-compiled kernel.
The process snapshots its caller-owned GPU mappings before commit and after
exact completion.  Inputs, outputs, and every trailing output byte are compared
bit-for-bit (768 bytes in the original images and 3,840 in the multi-load
images).  No Apple binary or Apple-authored program is inspected.

On the T8132 macOS guest:

```sh
sh build_guest.sh
sh run_guest_matrix.sh m4-YYYYMMDD-run01
sh run_guest_matrix.sh m4-YYYYMMDD-reverse reverse
sh run_guest_matrix.sh m4-YYYYMMDD-multiload multiload-forward
sh run_guest_matrix.sh m4-YYYYMMDD-multiload-reverse multiload-reverse
sh run_guest_matrix.sh m4-YYYYMMDD-loadscaling loadscaling-forward
sh run_guest_matrix.sh m4-YYYYMMDD-loadscaling-reverse loadscaling-reverse
sh run_guest_matrix.sh m4-YYYYMMDD-addressing addressing-forward
sh run_guest_matrix.sh m4-YYYYMMDD-addressing-reverse addressing-reverse
```

The matrix cases are `store1`, `copy2`, `uadd7`, `xorimm`, `andimm`, `fanout`,
`add3`, `iadd3`, `xor3`, `xoradd3`, `xorxor3`, `addxor3`, `andadd3`, `fmul3`,
`fconst3`, `dag3`, `reuse3`, and `mix4`. Each case runs in a fresh process so its first
archive block and first launch/resource records can be compared without an
append-only-cache history. The reverse-order mode checks whether prior runtime
compiler/cache activity contaminates that fresh-process result. See
[RESULTS.md](RESULTS.md) for the repeated
T8132 audit and the resulting bring-up constraints.

The focused multi-load order adds `load2_reduce`, `load2_reuse`, and
`load10_reduce` beside the `copy2` control.  All keep the same two-buffer
interface, rank-1 grid, and single terminal store while reading separated
64-word planes from one input resource.  Analyze those focused captures with
`analyze.py RUN --case-set multiload`, optionally adding a reverse-order run
with `--repeat`.

For the focused sets the analyzer also extracts the aligned archive main,
checks its complete capture-pinned size/SHA-256, and emits a semantic-neutral
device-load census: raw instruction bytes, main offset, framing bytes,
`extmode >> 1` destination, binding, index byte, and raw producer token.  It
does not assign names to the newly observed `91:00` and `d1:00` token classes.
Repeat analysis also gates identical `source.sha256` and `build-metadata.txt`
when both captures provide them, while reporting unavailable provenance for
older capture directories rather than rejecting them.

The load-scaling order adds a far-offset two-load control and 3/4/6/8-load
reductions.  It separates offset-literal pressure from load/result pressure and
is selected in the analyzer with `--case-set loadscaling`.  Both focused case
sets have forward/reverse byte-for-byte package gates documented in
[RESULTS.md](RESULTS.md).

The addressing order adds one-load `i+1` and `3*i+1` copies, paired `+255` and
`+256` two-load reductions, and a nine-load reduction between the existing
load8/load10 controls.  It checks computed addressing separately from package
state and the load-pressure tier.  The observed `0xff/0x100` transition is a
native compiler/package policy boundary, not a claimed Apple9 IADD hardware
limit.  The load-scaling gate fixes the reference `load2_far` main, launch, and
`u4 = 0x240` state; the addressing gate requires `load2_off256` to use that
same main/launch profile with `u4 = 0x100`.  Reproduce the exact main,
output/guard, relationship, provenance, and forward/reverse package gates with:

```sh
python3 analyze.py raw/runs/m4-20260830-addressing01 \
  --case-set addressing \
  --repeat raw/runs/m4-20260830-addressing-reverse
```
