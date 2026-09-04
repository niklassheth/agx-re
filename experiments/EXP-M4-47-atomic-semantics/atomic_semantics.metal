// Own-source Apple9/T8132 atomic probes.
//
// Each indexed kernel gives every lane a distinct destination so the complete
// result has an exact CPU oracle.  The contended kernels deliberately use one
// threadgroup; their return-value permutation is checked separately.
#include <metal_stdlib>
using namespace metal;

#define DEV_U_KERNEL(name, fetch, tag)                                        \
kernel void name(device uint4 *out [[buffer(0)]],                             \
                 device atomic_uint *target [[buffer(1)]],                    \
                 device const uint *value [[buffer(2)]],                      \
                 uint gid [[thread_position_in_grid]])                        \
{                                                                             \
    uint old = fetch(&target[gid], value[gid], memory_order_relaxed);          \
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);       \
    out[gid] = uint4(old, now, value[gid], tag | gid);                         \
}

DEV_U_KERNEL(dev_add, atomic_fetch_add_explicit, 0x10000000u)
DEV_U_KERNEL(dev_sub, atomic_fetch_sub_explicit, 0x11000000u)
DEV_U_KERNEL(dev_and, atomic_fetch_and_explicit, 0x12000000u)
DEV_U_KERNEL(dev_or,  atomic_fetch_or_explicit,  0x13000000u)
DEV_U_KERNEL(dev_xor, atomic_fetch_xor_explicit, 0x14000000u)
DEV_U_KERNEL(dev_umin, atomic_fetch_min_explicit, 0x15000000u)
DEV_U_KERNEL(dev_umax, atomic_fetch_max_explicit, 0x16000000u)
DEV_U_KERNEL(dev_xchg, atomic_exchange_explicit, 0x17000000u)

#define DEV_S_KERNEL(name, fetch, tag)                                        \
kernel void name(device uint4 *out [[buffer(0)]],                             \
                 device atomic_int *target [[buffer(1)]],                     \
                 device const int *value [[buffer(2)]],                       \
                 uint gid [[thread_position_in_grid]])                        \
{                                                                             \
    int old = fetch(&target[gid], value[gid], memory_order_relaxed);           \
    int now = atomic_load_explicit(&target[gid], memory_order_relaxed);        \
    out[gid] = uint4(as_type<uint>(old), as_type<uint>(now),                   \
                     as_type<uint>(value[gid]), tag | gid);                    \
}

DEV_S_KERNEL(dev_imin, atomic_fetch_min_explicit, 0x18000000u)
DEV_S_KERNEL(dev_imax, atomic_fetch_max_explicit, 0x19000000u)

kernel void dev_cmpxchg(device uint4 *out [[buffer(0)]],
                        device atomic_uint *target [[buffer(1)]],
                        device const uint2 *pair [[buffer(2)]],
                        uint gid [[thread_position_in_grid]])
{
    uint expected = pair[gid].x;
    uint desired = pair[gid].y;
    bool success = atomic_compare_exchange_weak_explicit(
        &target[gid], &expected, desired, memory_order_relaxed,
        memory_order_relaxed);
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(expected, now, success ? 1u : 0u, 0x1a000000u | gid);
}

kernel void dev_noret(device uint4 *out [[buffer(0)]],
                       device atomic_uint *target [[buffer(1)]],
                       device const uint *value [[buffer(2)]],
                       uint gid [[thread_position_in_grid]])
{
    atomic_fetch_add_explicit(&target[gid], value[gid], memory_order_relaxed);
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(now, value[gid], gid ^ 0x55u, 0x1b000000u | gid);
}

kernel void dev_return_fanout(device uint4 *out [[buffer(0)]],
                              device atomic_uint *target [[buffer(1)]],
                              device const uint *value [[buffer(2)]],
                              uint gid [[thread_position_in_grid]])
{
    uint old = atomic_fetch_xor_explicit(&target[gid], value[gid],
                                         memory_order_relaxed);
    uint a = old + 0x10203u;
    uint b = old ^ 0xa5a5a5a5u;
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(a, b, now, 0x1c000000u | gid);
}

kernel void dev_dynamic_index(device uint4 *out [[buffer(0)]],
                              device atomic_uint *target [[buffer(1)]],
                              device const uint2 *input [[buffer(2)]],
                              uint gid [[thread_position_in_grid]])
{
    uint index = input[gid].x;
    uint value = input[gid].y;
    uint old = atomic_fetch_add_explicit(&target[index], value,
                                         memory_order_relaxed);
    // Keep both address and operand live after the atomic.
    out[gid] = uint4(old, index, value, index * 17u + value);
}

kernel void dev_loop(device uint4 *out [[buffer(0)]],
                     device atomic_uint *target [[buffer(1)]],
                     device const uint *count [[buffer(2)]],
                     uint gid [[thread_position_in_grid]])
{
    uint last = 0, i = 0;
    for (; i < count[gid]; ++i)
        last = atomic_fetch_add_explicit(&target[gid], i + 1u,
                                         memory_order_relaxed);
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(last, now, i, 0x1d000000u | gid);
}

kernel void dev_if(device uint4 *out [[buffer(0)]],
                   device atomic_uint *target [[buffer(1)]],
                   device const uint *value [[buffer(2)]],
                   uint gid [[thread_position_in_grid]])
{
    uint old = 0xeeeeeeeeu;
    if (((gid ^ value[gid]) & 1u) != 0u)
        old = atomic_fetch_or_explicit(&target[gid], value[gid],
                                       memory_order_relaxed);
    uint now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(old, now, value[gid], 0x1e000000u | gid);
}

kernel void dev_contended_add(device uint *out [[buffer(0)]],
                              device atomic_uint *target [[buffer(1)]],
                              uint lid [[thread_position_in_threadgroup]])
{
    uint old = atomic_fetch_add_explicit(&target[0], 1u,
                                         memory_order_relaxed);
    out[lid] = old;
    threadgroup_barrier(mem_flags::mem_device);
    if (lid == 0)
        out[16] = atomic_load_explicit(&target[0], memory_order_relaxed);
}

kernel void tg_contended_add(device uint *out [[buffer(0)]],
                             uint lid [[thread_position_in_threadgroup]])
{
    threadgroup atomic_uint counter;
    if (lid == 0)
        atomic_store_explicit(&counter, 0u, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint old = atomic_fetch_add_explicit(&counter, 1u, memory_order_relaxed);
    out[lid] = old;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if (lid == 0)
        out[16] = atomic_load_explicit(&counter, memory_order_relaxed);
}

kernel void tg_ops(device uint4 *out [[buffer(0)]],
                   device const uint *input [[buffer(1)]],
                   uint lid [[thread_position_in_threadgroup]])
{
    threadgroup atomic_uint a[16];
    threadgroup atomic_uint b[16];
    threadgroup atomic_uint c[16];
    threadgroup atomic_uint d[16];
    atomic_store_explicit(&a[lid], 100u + lid, memory_order_relaxed);
    atomic_store_explicit(&b[lid], 0xf0f0u ^ lid, memory_order_relaxed);
    atomic_store_explicit(&c[lid], 100u + lid, memory_order_relaxed);
    atomic_store_explicit(&d[lid], 100u + lid, memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint x = input[lid];
    uint old_a = atomic_fetch_sub_explicit(&a[lid], x, memory_order_relaxed);
    uint old_b = atomic_fetch_xor_explicit(&b[lid], x, memory_order_relaxed);
    uint old_c = atomic_fetch_min_explicit(&c[lid], x, memory_order_relaxed);
    uint old_d = atomic_fetch_max_explicit(&d[lid], x, memory_order_relaxed);
    out[lid] = uint4(old_a, old_b, old_c, old_d);
}

kernel void tg_cmpxchg(device uint4 *out [[buffer(0)]],
                       device const uint2 *pair [[buffer(1)]],
                       uint lid [[thread_position_in_threadgroup]])
{
    threadgroup atomic_uint target[16];
    atomic_store_explicit(&target[lid], 0x7000u + lid,
                          memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    uint expected = pair[lid].x;
    bool success = atomic_compare_exchange_weak_explicit(
        &target[lid], &expected, pair[lid].y, memory_order_relaxed,
        memory_order_relaxed);
    uint now = atomic_load_explicit(&target[lid], memory_order_relaxed);
    out[lid] = uint4(expected, now, success ? 1u : 0u,
                     0x20000000u | lid);
}

kernel void dev_fadd(device uint4 *out [[buffer(0)]],
                     device atomic_float *target [[buffer(1)]],
                     device const float *value [[buffer(2)]],
                     uint gid [[thread_position_in_grid]])
{
    float old = atomic_fetch_add_explicit(&target[gid], value[gid],
                                          memory_order_relaxed);
    float now = atomic_load_explicit(&target[gid], memory_order_relaxed);
    out[gid] = uint4(as_type<uint>(old), as_type<uint>(now),
                     as_type<uint>(value[gid]), 0x1f000000u | gid);
}
