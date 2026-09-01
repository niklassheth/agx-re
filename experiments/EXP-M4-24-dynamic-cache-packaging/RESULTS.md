# EXP-M4-24: render pipeline/archive lifetime on T8132

This experiment uses caller-owned runtime Metal shaders and snapshots only the
caller's public GPU mappings.  It does not inspect Apple binaries.

## Result

T8132 keeps `usc_exec_base` fixed at `0x10000000000` while render pipelines are
created and used.  Executable archive contents and pipeline state have distinct
lifetimes:

- The process has one append-only archive BO at `0x10000000000`.
- Creating the first pipeline appends its vertex and fragment program blocks.
- Creating an identical pipeline allocates no BO and changes no byte in any
  captured mapping.  The executable stages and state are interned.
- Creating a pipeline with the same vertex shader and a distinct fragment
  shader appends only one program block.  The vertex program is reused.
- Each distinct simple pipeline adds a separate `0x40`-byte state record in
  the state BO.  The two records in this experiment are byte-identical because
  their non-shader state is identical.
- First execution lazily materializes the larger runtime/compiler support
  closure in the same archive.  A fragment pipeline created afterward still
  appends at the archive tail and executes correctly.

Both colors rendered exactly in the late-creation run:

```
DYNAMIC_STATE_DRAW after-draw-a0 ... pixel=bf8040ff exact=1
DYNAMIC_STATE_DRAW after-draw-b  ... pixel=8040bfff exact=1
DYNAMIC_STATE_RESULT exact=1
```

### Held A/B/A command selection

A second run held three commands from one process immediately before their
doorbells, after each earlier command had completed.  The same context-7 DVA
`0x10000180000` resolved to the same PTE (`0xc0010156b14c8b`) and physical
page (`0x10156b14000`) for B and the following A.  Across that whole 16-KiB
caller page, exactly two bytes changed, at `+0x28a`:

```
B: 77 01 2a 0b 00 00 00
A: 77 01 aa 07 00 00 00
```

Interpreted as the observed little-endian compact field, this is
`0x0b2a -> 0x07aa`.  The surrounding instruction, DVA, PTE, physical backing,
queue USC base, and executable archive stayed fixed.  Thus command selection
rewrites a caller-owned compact call/selector in stable pipeline state; it
does not select a new queue `usc_exec_base` or rebind a new archive BO.

The capture does not by itself assign a semantic name to every surrounding
byte, and in particular it does not make the unrelated state-packet length at
`+0x14` an archive selector.

## Driver model implied by the capture

The render compiler package is not a per-pipeline fixed-VA image.  The native
model is:

1. one queue/process-rooted executable archive at a fixed USC base;
2. content-addressed, append-only program blocks shared across pipelines;
3. separately allocated pipeline/dynamic-caching state records;
4. stable physical backing for the active archive and caller state;
5. command-visible selector updates only after prior users retire;
6. ordinary BO lifetime retention until every referencing command completes;
7. full-address executable/function state for programs that overflow the
   compact archive window (covered separately by EXP-M4-22).

This is the model Mesa should implement.  Rebinding a new monolithic package
at one logical DVA for each pipeline is neither necessary nor native.

## Mesa implementation and hardware validation

The T8132 Mesa branch now uses one permanently bound resident package at the
fixed logical render entry. Immutable source packages may live at arbitrary
storage VAs. On a selection change Mesa waits for the preceding resident user,
then:

1. reuses a byte-identical complete stage block when present;
2. otherwise appends the block to the resident 64-KiB archive;
3. copies the selected launch/descriptors/state outside that archive; and
4. patches the fragment, support, and vertex compact calls.

The interning comparison includes the block header and constant program, not
only the main bytes. Active Gallium batches pin source packages against LRU
eviction. A screen-wide timeline fence and lock serialize selection across
contexts. If the compact archive is full, Mesa waits for the old user and
rebuilds the same physical resident BO in place around the selected package;
the queue base and logical mapping remain unchanged.

The five-submit A/B/A/A/B hardware gate observed:

```
A fragment call = 0x07aa
B fragment call = 0x192aa
shared support  = 0x0aaa
shared vertex   = 0x0daa
archive tail    = 0xc9c0
```

A and B produced stable, distinct attachment hashes on both uses. The second
A made no resident install. The same sequence passed while alternating two
independent EGL/Gallium contexts. A forced `0xc980` test limit made every A/B
change take the in-place rollover path, and all five submissions still matched
the corresponding A/B hashes.

This covers the compact archive's native lifetime behavior. EXP-M4-22 also
shows that macOS can place very large/visible-function programs in ordinary
full-address executable BOs while retaining the fixed base. The ordinary
render-main trampoline/state encoding for that path remains an explicit
research gap; synchronized compact-archive rollover cannot make one
indivisible executable closure larger than 64 KiB fit.

## Artifacts

- `work/maps_dynamic_state_late/`: late pipeline-B snapshots
- `work/trace_dynamic_state_late.log`: ordered BO activity
- `../../tools/iotrace/iohello_render_dynamic_state.m`: caller-owned source
- held B capture SHA-256:
  `11666109a7c370e8143f087f6ba6f72878712deb6bc41745e5567544bdf22b5a`
- held A capture SHA-256:
  `c53a6cb4cb4ba054dd23a65decb4d8c3dd20c0f694bc49f6f88415ea0f254160`
- `../../tools/iotrace/iohello_render_pipeline_hold.m`: caller-owned held
  A/B/A source
- Mesa append/intern log:
  `logs/t8132_mesa_dynamic_cache_archive_intern_20260827_052029.log`
- Mesa two-context log:
  `logs/t8132_mesa_dynamic_cache_two_contexts_20260827_052450.log`
- Mesa forced-rollover log:
  `logs/t8132_mesa_dynamic_cache_forced_rollover_20260827_052651.log`
