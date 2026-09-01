# EXP-M4-20 — Minimal Apple9 render-compiler ISA and lifetime matrix

This experiment establishes the instruction and Dynamic-Caching contracts for
the first Mesa-generated Apple9 vertex/fragment pair.  It deliberately starts
with a bufferless triangle so vertex-fetch and texture descriptors are not
mixed into the first compiler milestone.

## Clean-room boundary

Every shader in this directory is our own Metal source.  macOS compiles it
through the public Metal API while running under m1n1's `run_guest.py`
hypervisor route.  We inspect and splice only the resulting caller-owned
archives and read back pixels produced by our own draw.  No proprietary
executable is disassembled or decompiled.

## Minimal compiler surface

The first useful shaded triangle needs these families:

| Stage | Semantic operation | Apple9 family |
|---|---|---|
| VS | vertex ID | `get_sr` (`0xdd`) |
| VS | position/colour construction | integer select, float ALU, immediates |
| VS | position + user-varying export | `vary_store` |
| FS | smooth/linear varying input | `iter`; perspective also uses reciprocal + `fmul` |
| FS | arithmetic/select | shared scalar Apple9 ALU families |
| FS | output conversion | `frag_color_pack` |
| FS | tilebuffer access/output | `frag_tile_setup`, `frag_color_store` |
| both | bounded program end | `stop` plus out-of-band code size |

The compiler should initially support one `float4 [[position]]`, one
`float4` varying, one BGRA/RGBA8 render target, no discard/depth/MSAA, and no
control flow.  Texture sampling, vertex buffers, depth, blending, and multiple
render targets are later milestones.

## Why the matrix has fanout variants

Apple9 register numbers are not the whole operand contract.  Producer state,
consumer route state, and per-source release state can make an instruction
produce the right immediate result while destroying a value needed later.
The shader pairs in `render_lifetime.metal` preserve the visible operation but
change whether values are consumed once, fanned out, or routed through ALU and
select chains.  `analyze_render_matrix.py` inventories each machine program
and reports every stage-specific instruction with its raw bytes and fields.

Hardware splices must keep the instruction opcode/register tuple fixed, mutate
one candidate state field, and compare all rendered pixels.  A compiler
correlation is not promoted to a semantic rule without this execution test.

## Capture

The device-side directory needs `shdump`, `agxrender`, and `agxparse.py` from
the repository's public clean-room tools.  Then:

```sh
./capture_guest.sh .
```

Copy `captures/` back to this directory and run:

```sh
python3 analyze_render_matrix.py captures
```

`splice_render.py` applies stage-relative mutations to a copied archive and
prints a pixel hash plus representative pixels.  It is used only after the
capture identifies exact instruction offsets.
