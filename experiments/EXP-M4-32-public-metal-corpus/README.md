# EXP-M4-32: public Metal corpus census

This experiment compiles a large, pinned corpus of permissively licensed public
Metal compute shaders with the native Metal compiler on T8132, materializes one
caller-owned binary archive per exported kernel, extracts each Apple9
`_agc.main`, and searches the emitted instructions for counterexamples to the
candidate-route rules developed in EXP-M4-31.

It is deliberately separate from the controlled own-source experiments.  The
public corpus is a discovery and contradiction tool: pipeline acceptance proves
that Metal considers an encoding valid, but the kernels are not dispatched and
do not have independent output oracles.  Any semantic hypothesis discovered
here still needs a minimal own-source execution and, where necessary, a hardware
ablation.

## Pinned sources

| Corpus | Commit | License | Metal translation units | Native pipelines |
|---|---|---:|---:|---:|
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | `e4b9af007beae34abba094cefd187658e89bbac8` | MIT | 20 | 961 |
| [PyTorch](https://github.com/pytorch/pytorch) | `76ba5accdec61a3cf2fd2e7074bd0e94faa1c1fa` | BSD-3-Clause | 49 | 16,879 |
| [MLX](https://github.com/ml-explore/mlx) | `37c26e5755da637255d57ea34b4879196a485301` | MIT | 42 | 17,323 |

`bundled/manifest.json` records every original translation unit, source hash,
mechanically produced bundle hash, and recursively resolved local-header hash.
The upstream sources are not copied into this repository.

## Method

The macOS 26.6.2 research guest exposes `newLibraryWithSource` but does not have
the offline `metal` command.  `bundle_corpora.py` therefore resolves only
project-local includes into self-contained source strings.  SDK headers remain
ordinary includes and are resolved by Metal.  No shader logic is rewritten.

`native_corpus_compiler.m` then:

1. Compiles one bundled translation unit as Metal 4.0 with fast math.
2. Enumerates every exported function.
3. Specializes function constants using the source-declared defaults.
4. Creates a compute pipeline and one binary archive per kernel.
5. Reopens the pipeline with `MTLPipelineOptionFailOnBinaryArchiveMiss`.

`analyze_corpus.py` deduplicates stage mains, conservatively tokenizes them, and
records route-bearing instruction windows.  A known instruction length without
a matching semantic descriptor is counted as `length-only`; an unknown length
ends that program's usable prefix.  Route evidence is admitted only from a
matched instruction descriptor before that boundary.  The strongest summary is
reported separately for programs whose entire main has both complete lengths
and complete descriptors.

Large generated inputs, archives, and full event logs are ignored by Git.
`dump_assembly.py` writes `ASSEMBLY.jsonl.zst`, a deduplicated ledger containing
every decoded record, length-only record, undecoded tail, and pipeline mapping;
`ASSEMBLY_INDEX.json` pins its hash and counts.  The small committed outputs are
the index, `CORPUS_CENSUS.json`, `SELECTED_WITNESSES.json`, and `RESULTS.md`.

## Reproduction

```sh
python3 bundle_corpora.py
python3 run_remote.py --run native-metal4-v2 --corpus llama.cpp
python3 run_remote.py --run native-metal4-pytorch-v2 --corpus pytorch
python3 run_remote.py --run native-metal4-mlx-v1 --corpus mlx
python3 analyze_corpus.py
python3 analyze_additional_route_fields.py
python3 analyze_qvm_route7.py
python3 select_witnesses.py
python3 dump_assembly.py
```

`qvm_route7_minimal.metal` is an own-source reduction of MLX's four-bit
`qouter` expression.  Its pinned native archives and hashes are listed in
`qvm_route7_minimal_manifest.json`; `analyze_qvm_route7.py` compares those
programs with the three apparent-route-7 public-corpus mains and writes
`QVM_ROUTE7_AUDIT.json`.

The native runs used T8132/macOS 26.6.2 build 25G83 on the Apple M4 research
guest.  See `RESULTS.md` for the evidence and current interpretation.
