# EXP-M4-28: native Apple9 compute synchronization and control flow

This own-source experiment isolates compute features that the current Apple9
compiler and package model do not yet cover: threadgroup memory, barriers,
divergent control flow, bounded loops, and device atomics. It uses only public
Metal/Foundation APIs and runtime-compiled MSL.

Every case runs in a fresh process, creates a fresh library and pipeline,
dispatches exactly 64 lanes as two 32-lane threadgroups, and submits one
command buffer. The binary checks the entire 4-KiB output against an
independent CPU oracle and verifies that all 4 KiB of input are immutable. It
writes pre/post input, pre/post output, and `expected.bin` into `raw/` for the
later trace analyzer.

## Cases and hypotheses

| Case | Deliberate behavior | Exact hypothesis |
|---|---|---|
| `shared_exchange` | One threadgroup write, barrier, and permuted peer read in each of two groups | The barrier publishes every lane's write within its group, and scratch storage is isolated between groups. |
| `shared_two_phase` | Populate scratch, read two peers, barrier, overwrite scratch, barrier, read a new peer | Reusing the same threadgroup allocation across phases preserves the two explicit read/write boundaries without stale or cross-group data. |
| `divergent_select` | Four-way lane selector feeding a pure-ALU `if/else` and one selected value | Existing Apple9 evidence predicts compare/select predication; this case verifies that branchless per-lane selection, not a forward branch/reconvergence encoding. |
| `divergent_loop` | A runtime device load selects one through sixty-four iterations per lane, with a divergent branch inside the loop | The tested values are bounded, but the shader cannot infer that range; loop active masks, a retained back edge, and per-iteration merge state must produce the exact per-lane result. |
| `atomic_sum` | All 64 lanes add distinct values into one device `atomic_uint` | The final unsigned sum is deterministic and only output word zero changes. |
| `atomic_or` | All 64 lanes select one bit from rotated input and OR it into one device `atomic_uint` | The final union of selected bits is deterministic and only output word zero changes. |

The atomic kernels intentionally discard `atomic_fetch_*` return values. Their
execution order is not deterministic and this experiment makes no claim about
that order. Only the commutative final state, full input immutability, and the
untouched output guard are asserted.

The four non-atomic cases write exactly the first 64 output words and retain
`0xcccccccc` in the remaining 960 words. Atomic cases start word zero from a
case-specific nonzero value, update only that word, and retain
`0xcccccccc` in the remaining 1,023 words. The shared-memory cases allocate
exactly 128 bytes at `[[threadgroup(0)]]`.

## Capture preparation

Copy the files in this directory to the macOS guest. Copy the canonical
tracer source from EXP-M4-26 into the same directory as `iotrace.c`; the build
script fails closed if it is absent. Then run:

```sh
./build_guest.sh
```

Collect both orders under distinct run IDs:

```sh
./run_guest_matrix.sh sync-cfg-forward forward
./run_guest_matrix.sh sync-cfg-reverse reverse
```

Each script invocation launches the matrix binary once per case, so no Metal
pipeline, command queue, resource, or process state is reused between cases.
This directory only prepares the experiment; creating it does not access the
target.

On a non-macOS development host, `./validate_host.py` independently rebuilds
all six CPU oracles, checks their pinned full-image SHA-256 values and exact
changed-word sets, and verifies that the source and forward/reverse runner
matrices agree. It does not compile MSL or access hardware.

## Capture order matrix

| Position | Forward | Reverse |
|---:|---|---|
| 1 | `shared_exchange` | `atomic_or` |
| 2 | `shared_two_phase` | `atomic_sum` |
| 3 | `divergent_select` | `divergent_loop` |
| 4 | `divergent_loop` | `divergent_select` |
| 5 | `atomic_sum` | `shared_two_phase` |
| 6 | `atomic_or` | `shared_exchange` |

Forward/reverse agreement is required before treating a package or ISA byte
as case-specific. The opposite order also makes accidental dependence on a
previous compilation or allocation pattern easier to detect.

## Required analyzer contract

The later analyzer must fail closed unless every case has:

- zero `run.status`, empty `stderr.log`, and exactly one
  `NATIVE_COMPUTE_SYNC_CFG_OK` marker;
- `grid=64`, `local=32`, and `groups=2` in the source log;
- two complete tracer snapshots without truncation;
- byte-identical 4-KiB pre/post input images;
- a post-output image byte-identical to both `expected.bin` and an
  independently reconstructed analyzer oracle;
- exactly 64 changed output words for non-atomic cases or one changed word for
  atomic cases, with every guard word retained exactly.

For each case and capture order, extract the exact main, constant program,
launch, state, resource table, CDM record, register count, and normalized
package identity. The synchronization cases should identify threadgroup
addressing and barrier instruction boundaries without naming unknown fields.
The control-flow cases should recover block boundaries, branch targets,
reconvergence/merge behavior, and loop back edges without assuming G17
encodings. Atomic cases should distinguish the resource access and atomic
operation from ordinary device loads/stores; final memory correctness is the
semantic gate, not command retirement or a guessed instruction name.

Useful comparisons are:

1. `shared_exchange` versus `shared_two_phase` for barrier count, scratch
   addressing, and any launch allocation change.
2. `divergent_select` versus `divergent_loop` for predicated selection versus
   forward loop exits, back edges, reconvergence, and active-mask handling.
3. `atomic_sum` versus `atomic_or` for the operation field while holding the
   device-atomic resource shape constant.
4. Every forward capture versus its reverse counterpart byte-for-byte after
   address normalization.

## Results

Both capture orders passed the fail-closed analyzer.  Reversing the primary
and repeat inputs produces byte-identical deterministic JSON with SHA-256
`df5d23e2a6760ae3331027834ab08d14e1bdf46a94cea9038cfc0443593b8341`.
All six complete 4-KiB input/output oracles and normalized caller packages
agree across process order.

The useful implementation boundaries are:

- `atomic_sum` and `atomic_or` reuse the existing stateless two-buffer launch,
  low constant program, low CDM record, and input/output resource table.  The
  atomic instruction's byte-12 discriminator is `0x20` for add and `0x2c` for
  OR.  Their output resource is a four-byte constant-address read/modify/write
  target, not a dense 64-word output.
- `shared_exchange` has one threadgroup store, barrier at main `+0x54`, and
  threadgroup load.  `shared_two_phase` has barriers at `+0xa0`, `+0x150`, and
  `+0x164`.  Both request exactly 128 threadgroup bytes and carry resource
  qword 4 equal to `0x80000000`.
- `divergent_select` is branchless in this native main.  `divergent_loop` has
  a forward exit to `+0x134` and back edge to `+0x46`; displacements are
  relative to the instruction start.
- The precommit CDM terminator is zero.  Completion changes only CDM byte
  `+0x2f`, to form `0x40000000`.

The caller dump does not contain firmware Work.  The analyzer therefore
reports only caller-derived public inputs to the later Work encoder and makes
no claim that a Work image was captured.

The first Mesa integration gate covers both atomic programs through ordinary
Gallium NIR and the DRM UAPI.  A cold T8132 run executed four dispatches in
sum-to-OR and OR-to-sum orders.  It accepted an exact four-byte output binding,
rejected three-byte and unaligned bindings without publication, and matched
the complete independently computed 4-KiB outputs while preserving every
input byte and output guard word.
