// Own-source probes for the record immediately preceding returned device
// atomics.  Separate input bindings discourage load coalescing and let the
// native compiler choose scoreboard slots under controlled pending pressure.
#include <metal_stdlib>
using namespace metal;

#define SLOT_PROBE(name, selected)                                            \
kernel void name(device uint4 *out [[buffer(0)]],                             \
                 device atomic_uint *target [[buffer(1)]],                    \
                 device const uint *a [[buffer(2)]],                          \
                 device const uint *b [[buffer(3)]],                          \
                 device const uint *c [[buffer(4)]],                          \
                 device const uint *d [[buffer(5)]],                          \
                 device const uint *e [[buffer(6)]],                          \
                 device const uint *f [[buffer(7)]],                          \
                 uint gid [[thread_position_in_grid]])                        \
{                                                                             \
    uint va = a[gid];                                                          \
    uint vb = b[gid];                                                          \
    uint vc = c[gid];                                                          \
    uint vd = d[gid];                                                          \
    uint ve = e[gid];                                                          \
    uint vf = f[gid];                                                          \
    uint old = atomic_fetch_add_explicit(&target[gid], selected,              \
                                          memory_order_relaxed);               \
    out[gid * 2 + 0] = uint4(old, va, vb, vc);                                \
    out[gid * 2 + 1] = uint4(vd, ve, vf,                                      \
                              va ^ (vb + vc) ^ (vd + ve + vf));                \
}

SLOT_PROBE(atomic_operand_a, va)
SLOT_PROBE(atomic_operand_b, vb)
SLOT_PROBE(atomic_operand_c, vc)
SLOT_PROBE(atomic_operand_d, vd)
SLOT_PROBE(atomic_operand_e, ve)
SLOT_PROBE(atomic_operand_f, vf)

// Keep several ordinary values live so Metal is free to allocate the
// immediate operand and returned value away from r0 if the form permits it.
kernel void atomic_immediate_pressure(device uint4 *out [[buffer(0)]],
                                      device atomic_uint *target [[buffer(1)]],
                                      device const uint4 *input [[buffer(2)]],
                                      uint gid [[thread_position_in_grid]])
{
    uint4 x = input[gid];
    uint old = atomic_fetch_add_explicit(&target[gid], 0x12345u,
                                          memory_order_relaxed);
    out[gid] = uint4(old, x.x + x.z, x.y ^ x.w,
                     (x.x * 3u) + (x.y * 5u) + x.z + x.w);
}

// Texture reads normally start their scoreboard allocation at slot 1 rather
// than the scalar-device-load preference of slot 6.  This asks whether the
// atomic-adjacent record follows that producer allocation.
kernel void atomic_texture_operand(device uint4 *out [[buffer(0)]],
                                   device atomic_uint *target [[buffer(1)]],
                                   texture2d<uint, access::read> input
                                      [[texture(0)]],
                                   uint2 gid [[thread_position_in_grid]])
{
    uint value = input.read(gid).x;
    uint old = atomic_fetch_add_explicit(&target[gid.y * input.get_width() +
                                                  gid.x],
                                          value, memory_order_relaxed);
    out[gid.y * input.get_width() + gid.x] =
       uint4(old, value, gid.x, gid.y);
}

// Keep the atomic return's first consumer as a scalar device store.  This is
// useful for result-slot mutations because that store selects a pending value
// by its associated GPR rather than carrying a separate scoreboard selector.
kernel void atomic_pending_direct_store(device uint *out [[buffer(0)]],
                                        device atomic_uint *target [[buffer(1)]],
                                        device const uint *input [[buffer(2)]],
                                        uint gid [[thread_position_in_grid]])
{
    uint operand = input[gid];
    uint old = atomic_fetch_add_explicit(&target[gid], operand,
                                          memory_order_relaxed);
    out[gid * 3 + 0] = old;
    out[gid * 3 + 1] = operand;
    out[gid * 3 + 2] = atomic_load_explicit(&target[gid],
                                             memory_order_relaxed);
}

// Retain the returned old value across several observable consumers.  The
// volatile stores prevent Metal from coalescing the duplicate scalar uses.
kernel void atomic_pending_fanout(device volatile uint *out [[buffer(0)]],
                                  device atomic_uint *target [[buffer(1)]],
                                  device const uint *input [[buffer(2)]],
                                  uint gid [[thread_position_in_grid]])
{
    uint operand = input[gid];
    uint old = atomic_fetch_xor_explicit(&target[gid], operand,
                                          memory_order_relaxed);
    out[gid * 5 + 0] = old;
    out[gid * 5 + 1] = old;
    out[gid * 5 + 2] = old + 0x10203u;
    out[gid * 5 + 3] = operand;
    out[gid * 5 + 4] = atomic_load_explicit(&target[gid],
                                             memory_order_relaxed);
}

// Keep six returned atomics pending simultaneously.  This recovers Metal's
// complete native atomic-result allocation order while every RMW operand is a
// directly pending scalar device load.
kernel void atomic_six_pending(device volatile uint *out [[buffer(0)]],
                               device atomic_uint *target [[buffer(1)]],
                               device const uint *a [[buffer(2)]],
                               device const uint *b [[buffer(3)]],
                               device const uint *c [[buffer(4)]],
                               device const uint *d [[buffer(5)]],
                               device const uint *e [[buffer(6)]],
                               device const uint *f [[buffer(7)]],
                               uint gid [[thread_position_in_grid]])
{
    uint v0 = a[gid], v1 = b[gid], v2 = c[gid];
    uint v3 = d[gid], v4 = e[gid], v5 = f[gid];
    uint base = gid * 6;
    uint o0 = atomic_fetch_add_explicit(&target[base + 0], v0,
                                         memory_order_relaxed);
    uint o1 = atomic_fetch_xor_explicit(&target[base + 1], v1,
                                         memory_order_relaxed);
    uint o2 = atomic_fetch_sub_explicit(&target[base + 2], v2,
                                         memory_order_relaxed);
    uint o3 = atomic_fetch_or_explicit(&target[base + 3], v3,
                                        memory_order_relaxed);
    uint o4 = atomic_fetch_and_explicit(&target[base + 4], v4,
                                         memory_order_relaxed);
    uint o5 = atomic_exchange_explicit(&target[base + 5], v5,
                                        memory_order_relaxed);
    uint obase = gid * 18;
    out[obase + 0] = o0; out[obase + 1] = o1;
    out[obase + 2] = o2; out[obase + 3] = o3;
    out[obase + 4] = o4; out[obase + 5] = o5;
    out[obase + 6] = v0; out[obase + 7] = v1;
    out[obase + 8] = v2; out[obase + 9] = v3;
    out[obase + 10] = v4; out[obase + 11] = v5;
    out[obase + 12] = atomic_load_explicit(&target[base + 0],
                                            memory_order_relaxed);
    out[obase + 13] = atomic_load_explicit(&target[base + 1],
                                            memory_order_relaxed);
    out[obase + 14] = atomic_load_explicit(&target[base + 2],
                                            memory_order_relaxed);
    out[obase + 15] = atomic_load_explicit(&target[base + 3],
                                            memory_order_relaxed);
    out[obase + 16] = atomic_load_explicit(&target[base + 4],
                                            memory_order_relaxed);
    out[obase + 17] = atomic_load_explicit(&target[base + 5],
                                            memory_order_relaxed);
}
