# Device-loaded index capture matrix

Status: completed in both forward and reverse fresh-process orders.  The exact
results and package classification are recorded in `DEVICE_INDEX_RESULTS.md`.

This isolated own-source matrix tests values loaded from device memory and then
used as addresses without changing the established EXP-M4-26 package matrix.
Every invocation uses a fresh process, checks the complete 4-KiB output image,
requires all input images to remain immutable, and leaves a 3,840-byte `0xcc`
output guard. Raw pre/post images and the independent CPU oracle are retained.

The eleven cases separate these questions:

| Case | Addressing question | Control relationship |
|---|---|---|
| `direct_copy` | `data[i]` | Baseline for identity index |
| `direct_affine` | `data[i*3+1]` | Baseline for loaded affine index |
| `index_identity` | `idx=indices[i]; data[idx]` | Output equals `direct_copy` |
| `index_identity_add0` | `(indices[i]+0)` | Expected to match `index_identity` |
| `index_permute` | Nonidentity device-loaded index | Prevents an accidental lane-index result |
| `index_permute_add1` | Nonidentity loaded `idx+1` | Address ALU cannot be optimized away |
| `index_affine` | `data[idx*3+1]` | Output equals `direct_affine` |
| `index_affine_permute` | Nonidentity `data[idx*3+1]` | Wrong gid-to-IMAD wiring cannot pass |
| `index_reuse_alu` | `data[idx]^idx` | Loaded index must reach address and ALU consumers |
| `index_reuse2` | Same loaded index addresses two BOs | Both loads affect every result |
| `index_chain` | `idx2=indices2[indices[i]]` | Two dependent device loads before the data load |

Identity cases use `indices[i]=i`. Nonidentity cases use
`indices[i]=(13*i+7)&63`; the second chain table uses
`indices2[i]=(5*i+11)&127`. All derived addresses are preflight bounds-checked.

Copy the canonical `iotrace.c` into the guest experiment directory. The build
refuses to proceed if it is absent, and the runner records its checksum.
On the T8132 macOS guest, from this experiment directory, run:

```sh
sh build_device_index_matrix.sh
sh run_device_index_matrix.sh m4-device-index-forward forward
sh run_device_index_matrix.sh m4-device-index-reverse reverse
```

Both capture roots should contain eleven zero `run.status` files. Preserve the
entire `captures/m4-device-index-*` directories for host analysis. Compare the
exact output/expected hashes for the three stated control relationships before
interpreting archive or instruction differences. Forward/reverse agreement is
the first-block/order-dependence gate. The analyzer now fails closed on all
eleven output oracles, every complete main and archive block, the four exact
package carriers, the complete device-load byte census, and full package-field
equality across the two orders:

```sh
python3 analyze.py raw/runs/m4-20260830-device-index-forward \
  --case-set device-index \
  --repeat raw/runs/m4-20260830-device-index-reverse
```
