# EXP-M4-22: T8132 executable-template rollover

## Question

Determine what native Metal does when caller-owned executable functions no
longer fit in G16's shared 64-KiB archive, and whether that condition changes
the queue's `usc_exec_base`.

The probe uses only public Metal APIs and runtime-compiled caller-authored MSL.
It does not inspect or disassemble Apple code.  Source is
`tools/iotrace/iohello_compute_visible_pressure.m` and
`tools/iotrace/iohello_render_visible_pressure.m`.

## Direct executable pressure

Each compute run creates N distinct `[[visible]] uint(uint)` functions, links
all of them into one pipeline with `MTLLinkedFunctions`, installs the final
function in a `MTLVisibleFunctionTable`, and calls it on hardware.  Every
function has a unique multiply/XOR body, so it requires an independently
addressable executable entry rather than another dispatch record for one
interned program.

Snapshots are taken after device creation, after pipeline linking, and after
execution.  The selected final function produced its exact expected value in
every tested run through N=16,384.

## Exact archive rollover

The fixed archive is at `0x10000000000`, size `0x10000`.  Its pre-link image
has nonzero extent `0x2242`.  Visible functions occupy 0x40-byte slots.

| Functions | Linked representation | Last selected code VA | Result |
| ---: | --- | ---: | --- |
| 256 | fixed archive, extent `0x6382` | archive resident | exact |
| 768 | fixed archive, extent `0xe382` | archive resident | exact |
| 881 | fixed archive, extent `0xff8b` | `0x1000000ff00` | exact |
| 882 | external executable at `0x10000080000` | `0x1000008dd00` | exact |
| 1,024 | external executable at `0x10000080000` | `0x10000090080` | exact |
| 16,384 | external executable at `0x10000080000` | `0x10000180080` | exact |

Thus 881 functions are the last set that fits this particular initialized
archive.  At 882, Metal does not partially overwrite, rotate the queue, or
change the base.  It keeps the fixed archive and relocates the linked-function
set into a separate executable object.  The object grows from a nonzero extent
of `0xddc3` at 882 functions to `0x100142` at 16,384 functions.

The function table contains the full 64-bit code VA.  For external sets the
function entries start at object offset `0xc0` and advance by `0x40`; the last
entries above match `base + 0xc0 + (N - 1) * 0x40` exactly.

## Executable code beyond the 4-GiB aperture

The decisive combined runs retain forty 128-MiB private buffers (5 GiB) before
linking the executable set.  Metal then places the external executable at
`0x101401c0000`, beyond the 4-GiB aperture rooted at `0x10000000000`:

| Functions | External allocation | Selected code VA | Result |
| ---: | ---: | ---: | --- |
| 1,024 | `0x101401c0000`, size `0x14000` | `0x101401d0080` | exact |
| 16,384 | `0x101401c0000`, size `0x104000` | `0x101402c0080` | exact |

The 1,024- and 16,384-function external object bytes are independently
identical with and without 5-GiB pressure; only their DVA changes.  The fixed
64-KiB archive remains at `0x10000000000`, and the process still opens one
`AGXAcceleratorG16G` client and issues one selector-7 registration.

This establishes two distinct executable-address paths:

1. Compact archive calls are relative to the stable `usc_exec_base` aperture.
2. Visible/linked function calls use a full 64-bit code VA and can execute
   caller code outside that aperture.

## Render-stage confirmation

The render probe links 1,024 distinct `[[visible]] float4(float4)` fragment
functions after the same 5-GiB allocation pressure.  The fragment visible
function table points to `0x101401d0080` in an external executable object at
`0x101401c0000`.  Drawing a full-screen triangle through the final function
completes exactly with BGRA pixel `40 33 ff ff`.

Therefore the full-address executable path is not compute-only.  It works from
the fragment stage and is directly relevant to G16 render packaging.

## Driver consequence

Changing `usc_exec_base` is unnecessary for dynamic Mesa shader code.  The
native-like design is:

1. Keep a small immutable archive/trampoline set inside the stable 4-GiB USC
   aperture.
2. Allocate arbitrary generated stage programs as ordinary executable BOs.
3. Put their full 64-bit entry addresses in per-pipeline state/function tables.
4. Have the fixed launch/template path call those addresses indirectly.
5. Retain each executable BO until all batches that reference it complete.

This preserves the existing DRM UAPI and avoids same-DVA archive aliasing,
queue recreation, and synchronized `usc_exec_base` generations.  The next
reverse-engineering target is the exact fixed trampoline and state-record
encoding used by ordinary non-API-visible vertex/fragment mains, so Mesa can
construct the same full-address transition without exposing Metal function
tables.

Selected traces and all three phase snapshots are retained in
`work/visible_pressure_selected.tar.gz`.
