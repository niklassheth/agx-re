# T8132 device-loaded-index results

The forward and reverse fresh-process matrices each completed all eleven
own-source Metal workloads with exact 4-KiB output images, immutable inputs,
and the complete 3,840-byte `0xcc` output guard intact.  Their source manifests,
build metadata, authored mains, archive blocks, package fields, normalized
resource tables, and CPU oracles are byte-identical across order.

The matrix contains eight byte-unique mains: the already-gated `direct_copy`
baseline plus seven additional main identities.  Cases sharing a main still
use different initialized index planes, so the semantic oracles distinguish
identity from permutation even when the compiled code is identical.

## Exact mains and semantic controls

| Case | Main bytes | Loads | Main SHA-256 |
| --- | ---: | ---: | --- |
| `direct_copy` | 36 | 1 | `67a99096b796c50e03431885914a3c828b44672fb95936b89a8ff0c2b3646199` |
| `direct_affine` | 56 | 1 | `4fa4f3517af232f62baa90c5e4a5d8e7bf22ad443aef27787c8c4ed991402945` |
| `index_identity` | 50 | 2 | `a49d45025192cc7cc158521006072fa2b19671361ca67959bd3a8051e1b5856d` |
| `index_identity_add0` | 50 | 2 | same as `index_identity` |
| `index_permute` | 50 | 2 | same as `index_identity` |
| `index_permute_add1` | 60 | 2 | `dc11ca2dac7a1668771425368336bbd2c0a99e8abae92655da773219e07c4444` |
| `index_affine` | 70 | 2 | `d0c67459ad98d572832764b2c2505c7021b5db0f41e6eff281b8dcf1a40f609a` |
| `index_affine_permute` | 70 | 2 | same as `index_affine` |
| `index_reuse_alu` | 60 | 2 | `fb1cfcdab417362906cee96f358eaab62a85d254221b3b654be8970ffe87e247` |
| `index_reuse2` | 88 | 3 | `85b1fe9b1f318cd77f2d5917ecacd76de338f26e312e69df62439db8a22bb3fd` |
| `index_chain` | 64 | 3 | `075e35c255ec023bb874d55983c9d3b71f264c6d59b5097cb7de4e15f28d8078` |

The complete guarded output SHA-256 identities are:

| Cases | Output SHA-256 |
| --- | --- |
| direct copy, identity, identity-add-zero | `a0fe97de6703d63ce1f6aedc4ab877496f4caac0bc958c133b7eb3b034899147` |
| direct affine, identity-index affine | `310b57232f625b10517fc87611ad82f21d99cc4ba5be8b89deaa13e790a12776` |
| permute | `3e1a9bd1184cb28e5f10ed4aebb2f5d325559f2e22417e030e6665ce88dd5e78` |
| permute plus one | `0fe2f4beaf712b2bfd613fed2c3f4a552eb1aac9e525bdf8def4aebdca738a86` |
| affine permutation | `070dac97d83fd8aa8876458c9e0ace90240d303c6d99783eb7ae268096ce3e25` |
| reuse in ALU | `c48cda6d8b8ac46099c758cf134d7d690472992e39434a1a5526a5f924fca033` |
| reuse across two BOs | `361cb1e7220c478b3cd5a6ccea01565aefe84e7877873d4df0586d73a45321f4` |
| dependent chain | `9f187429900498bbc3cb696567705e86294ec44642c45fac94ec6e8658489a61` |

The analyzer asserts three independent semantic equalities over complete
4-KiB CPU-oracle images:

- `direct_copy == index_identity == index_identity_add0`.
- `direct_affine == index_affine` with identity indices.
- The permutation cases do *not* reuse either identity oracle; each has its
  own hard-coded output hash.

It also reconstructs every output independently from the captured immutable
input planes and the eleven source formulas.  The negative controls require
`index_permute != direct_copy`, `index_permute_add1 != index_permute`, and
`index_affine_permute != direct_affine`, preventing an accidental global-ID
address path from satisfying only the equality controls.

`index_identity`, `index_identity_add0`, and `index_permute` have one identical
main.  `index_affine` and `index_affine_permute` likewise have one identical
main.  This proves that initialized device data changes semantics without
changing the pipeline package.

## Four complete package carriers

All cases share archive-header SHA-256
`9be8f59a1eee955c4cc2a6ed342143ee1ede7e5a861c34f22829f576dde497cc`,
low constant-program SHA-256
`9baa760c5185b9e5645bd1299e5ec948674258d6cbb0dc68b1394f1e45f3fd27`,
and direct-CDM SHA-256
`d7dbd6c1f7567204bc1962aff370d60d44e93b9ec239ea3b9d615152746665b4`.
The exact cases divide into four carriers:

| Carrier | Cases | Launch | Call | `+0x5a` | State | Reuse consequence |
| --- | --- | ---: | ---: | ---: | --- | --- |
| SSBO2 stateless | direct cases | `0x88` / `0xc0` | `+0x28` | `0x10` | absent | Reuse existing scalar-map SSBO2 carrier |
| SSBO3 state, small route | identity, permute, add1, reuse-ALU | `0xc4` / `0x100` | `+0x54` | `0x04` | `0x40` plus zeros | Byte-exact existing SSBO3 carrier |
| SSBO3 state, affine route | both affine-index cases | `0xc4` / `0x100` | `+0x54` | `0x00` | `0x40` plus zeros | Same SSBO3 interface, distinct observed launch variant |
| SSBO4 stateless | reuse2, chain | `0xa6` / `0xc0` | `+0x36` | `0x02` | absent | New stateless four-resource ABI |

The two launch sizes in each row are authored bytes and aligned allocation.
Every launch carries archive call `0x0007aa`; every byte after the authored
body in the captured `0x100` snapshot is zero.  Resource order is native Metal
argument order.  The normalized two-, three-, and four-pointer tables are also
hard-gated independently of process-local virtual addresses.

In particular, `index_permute` can reuse the existing SSBO3 package bytes.
Its native resource order is `indices, data, out`; Mesa's existing compact
binding permutation may map that to `2, 1, 0`.  Buffer-size reasoning remains
compiler/runtime metadata: the package table contains pointers, not bounds,
and a zero static access tail does not prove arbitrary device-loaded indices
are in range.

## Dependent-load byte correlations

The analyzer gates every complete 14-byte device-load encoding, not merely a
decoded subset.  Two repeatable correlations are useful for the compiler but
are not yet named as universal ISA semantics:

- Load byte 5 carries its high tag on the final dependent use of an ordinary
  computed index.  Identity's dependent load uses `0x80`; `index_reuse2` uses
  `0x00` then `0x80`; both dependent steps in `index_chain` use `0x80` for
  their respective loaded values.  In `index_reuse_alu`, the dependent load
  uses untagged `0x02` because that loaded index remains live for the XOR.
- Load byte 2 bit 1 is set on the first load which directly consumes a
  load-produced index.  `index_reuse2` gives `[set, clear]` for the first and
  second consumers of one index.  `index_chain` gives `[set, set]` because
  each load is the first consumer of a newly loaded value.  An intervening
  address ALU in the add-one and affine cases clears the correlation.

All 22 device loads in the eleven mains carry the same raw `51:01` token,
including all three loads in `index_chain`.  It is therefore not a unique SSA
producer identity, and the older independent-load ordinal token-pair rule must
not be extended to dependent chains.  Compiler provenance must model the
actual value chain separately from this raw scheduling tuple.

Reproduce the complete fail-closed audit with:

```sh
python3 -m py_compile analyze.py
python3 analyze.py raw/runs/m4-20260830-device-index-forward \
  --case-set device-index \
  --repeat raw/runs/m4-20260830-device-index-reverse
```
