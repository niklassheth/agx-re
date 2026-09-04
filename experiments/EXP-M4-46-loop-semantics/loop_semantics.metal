// Own-source Apple9/T8132 loop-control probes.
//
// The arithmetic is intentionally iteration-dependent so Metal cannot replace
// the loops with a simple closed form.  Each kernel writes four distinguishable
// words per lane, allowing the runner to check the entire result rather than
// command-buffer retirement alone.
#include <metal_stdlib>
using namespace metal;

static inline uint step(uint value, uint iteration)
{
    return value * 3u + (iteration ^ 0x35u);
}

kernel void while_top(device uint4 *out [[buffer(0)]],
                      device const uint *count [[buffer(1)]],
                      device const uint *aux [[buffer(2)]],
                      uint lane [[thread_position_in_grid]])
{
    uint i = 0, value = aux[lane] ^ 0x10203040u;
    while (i < count[lane]) {
        value = step(value, i);
        ++i;
    }
    out[lane] = uint4(value, i, count[lane], 0x10000000u | lane);
}

kernel void do_bottom(device uint4 *out [[buffer(0)]],
                      device const uint *count [[buffer(1)]],
                      device const uint *aux [[buffer(2)]],
                      uint lane [[thread_position_in_grid]])
{
    uint i = 0, value = aux[lane] ^ 0x20304050u;
    do {
        value = step(value, i);
        ++i;
    } while (i < count[lane]);
    out[lane] = uint4(value, i, count[lane], 0x20000000u | lane);
}

kernel void for_dynamic(device uint4 *out [[buffer(0)]],
                        device const uint *count [[buffer(1)]],
                        device const uint *aux [[buffer(2)]],
                        uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0x30405060u;
    uint i;
    for (i = 0; i < count[lane]; ++i)
        value = step(value, i);
    out[lane] = uint4(value, i, count[lane], 0x30000000u | lane);
}

kernel void loop_break(device uint4 *out [[buffer(0)]],
                       device const uint *count [[buffer(1)]],
                       device const uint *cut [[buffer(2)]],
                       uint lane [[thread_position_in_grid]])
{
    uint value = 0x40506070u ^ lane;
    uint executed = 0, i;
    for (i = 0; i < count[lane]; ++i) {
        if (i == cut[lane])
            break;
        value = step(value, i);
        ++executed;
    }
    out[lane] = uint4(value, i, executed, 0x40000000u | lane);
}

kernel void loop_continue(device uint4 *out [[buffer(0)]],
                          device const uint *count [[buffer(1)]],
                          device const uint *aux [[buffer(2)]],
                          uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0x50607080u;
    uint executed = 0;
    for (uint i = 0; i < count[lane]; ++i) {
        if (((i ^ lane) & 3u) == 1u)
            continue;
        value = step(value, i);
        ++executed;
    }
    out[lane] = uint4(value, count[lane], executed, 0x50000000u | lane);
}

kernel void if_inside_loop(device uint4 *out [[buffer(0)]],
                           device const uint *count [[buffer(1)]],
                           device const uint *aux [[buffer(2)]],
                           uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0x60708090u;
    uint then_count = 0;
    for (uint i = 0; i < count[lane]; ++i) {
        if (((i + lane) & 1u) != 0u) {
            value = step(value, i);
            ++then_count;
        } else {
            value = value * 5u - (i | 1u);
        }
    }
    out[lane] = uint4(value, count[lane], then_count,
                      0x60000000u | lane);
}

kernel void loop_inside_if(device uint4 *out [[buffer(0)]],
                           device const uint *count [[buffer(1)]],
                           device const uint *aux [[buffer(2)]],
                           uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0x708090a0u;
    uint executed = 0;
    if ((lane & 1u) != 0u) {
        for (uint i = 0; i < count[lane]; ++i) {
            value = step(value, i);
            ++executed;
        }
    } else {
        value ^= 0x00ff00ffu;
    }
    out[lane] = uint4(value, count[lane], executed,
                      0x70000000u | lane);
}

kernel void nested_loops(device uint4 *out [[buffer(0)]],
                         device const uint *outer_count [[buffer(1)]],
                         device const uint *inner_count [[buffer(2)]],
                         uint lane [[thread_position_in_grid]])
{
    uint value = 0x8090a0b0u ^ lane;
    uint executed = 0;
    for (uint i = 0; i < outer_count[lane]; ++i) {
        for (uint j = 0; j < inner_count[lane]; ++j) {
            value = step(value, i * 17u + j);
            ++executed;
        }
        value ^= i + 0x91u;
    }
    out[lane] = uint4(value, outer_count[lane], executed,
                      0x80000000u | lane);
}

kernel void carried_pair(device uint4 *out [[buffer(0)]],
                         device const uint *count [[buffer(1)]],
                         device const uint *seed [[buffer(2)]],
                         uint lane [[thread_position_in_grid]])
{
    uint a = seed[lane] ^ 0x91a2b3c4u;
    uint b = seed[lane] ^ 0x4c3b2a19u;
    uint i = 0;
    while (i < count[lane]) {
        uint next_a = b + i * 3u;
        uint next_b = a ^ (i * 17u + 1u);
        a = next_a;
        b = next_b;
        ++i;
    }
    out[lane] = uint4(a, b, i, 0x90000000u | lane);
}

kernel void carried_vector(device uint4 *out [[buffer(0)]],
                           device const uint *count [[buffer(1)]],
                           device const uint *seed [[buffer(2)]],
                           uint lane [[thread_position_in_grid]])
{
    uint4 value = uint4(seed[lane], seed[lane] ^ 0x11111111u,
                        seed[lane] ^ 0x22222222u,
                        seed[lane] ^ 0x33333333u);
    for (uint i = 0; i < count[lane]; ++i)
        value = value.yzwx * uint4(3u, 5u, 7u, 9u) + (i | 1u);
    value.w ^= lane;
    out[lane] = value;
}

kernel void nested_break_continue(device uint4 *out [[buffer(0)]],
                                  device const uint *outer_count [[buffer(1)]],
                                  device const uint *inner_count [[buffer(2)]],
                                  uint lane [[thread_position_in_grid]])
{
    uint value = 0xa0b0c0d0u ^ lane;
    uint visited = 0;
    for (uint i = 0; i < outer_count[lane]; ++i) {
        for (uint j = 0; j < inner_count[lane]; ++j) {
            if (((i + j + lane) & 3u) == 0u)
                continue;
            if (j == ((lane + 1u) & 3u))
                break;
            value = step(value, i * 17u + j);
            ++visited;
        }
        value ^= i + 0xb1u;
    }
    out[lane] = uint4(value, outer_count[lane], visited,
                      0xa0000000u | lane);
}

// Kept deliberately simple for a later instruction-boundary branch-target
// ablation.  The analyzer chooses a safe alternate target only after examining
// the actual native instruction stream.
kernel void pc_base_probe(device uint4 *out [[buffer(0)]],
                          device const uint *count [[buffer(1)]],
                          device const uint *aux [[buffer(2)]],
                          uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0xb0c0d0e0u;
    uint i = 0;
    while (i < count[lane]) {
        value = value * 3u + 7u;
        value ^= i + 0x123u;
        ++i;
    }
    out[lane] = uint4(value, i, count[lane], 0xb0000000u | lane);
}

// Canonical infinite NIR-style loop with a conditional exit, rather than a
// source-level while condition.  This checks whether Metal normalizes the two
// source shapes to the same mask/backedge machinery.
kernel void infinite_break(device uint4 *out [[buffer(0)]],
                           device const uint *count [[buffer(1)]],
                           device const uint *aux [[buffer(2)]],
                           uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0xc0d0e0f0u;
    uint i = 0;
    while (true) {
        if (i >= count[lane])
            break;
        value = step(value, i);
        ++i;
    }
    out[lane] = uint4(value, i, count[lane], 0xc0000000u | lane);
}

// A fresh device load is issued on every dynamic iteration.  The input is a
// fixed 16-word ring so the CPU oracle can cover arbitrary lane trip counts.
kernel void loop_device_load(device uint4 *out [[buffer(0)]],
                             device const uint *count [[buffer(1)]],
                             device const uint *aux [[buffer(2)]],
                             uint lane [[thread_position_in_grid]])
{
    uint value = 0xd0e0f001u ^ lane;
    uint executed = 0;
    for (uint i = 0; i < count[lane]; ++i) {
        uint loaded = aux[(i + lane) & 15u];
        value = step(value ^ loaded, i);
        ++executed;
    }
    out[lane] = uint4(value, count[lane], executed,
                      0xd0000000u | lane);
}

// Two independently dynamic conditions feed the latch.  The full corpus
// associates this shape with the 0x02 rather than 0x22 mask-update tail; this
// fresh executable case checks that relationship with an exact oracle.
kernel void compound_latch(device uint4 *out [[buffer(0)]],
                           device const uint *count [[buffer(1)]],
                           device const uint *aux [[buffer(2)]],
                           uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0xd1e2f304u;
    uint stop = aux[lane] & 31u;
    uint i = 0;
    while (i < count[lane] && i != stop) {
        value = step(value, i);
        ++i;
    }
    out[lane] = uint4(value, i, stop, 0xd1000000u | lane);
}

// Put break beneath another divergent conditional and make both sides of the
// outer condition observable.  This prevents source spelling alone from
// determining the native control-flow shape.
kernel void break_nested_if(device uint4 *out [[buffer(0)]],
                            device const uint *count [[buffer(1)]],
                            device const uint *aux [[buffer(2)]],
                            uint lane [[thread_position_in_grid]])
{
    uint value = 0xe0f00112u ^ lane;
    uint executed = 0;
    uint limit = aux[lane] & 31u;
    for (uint i = 0; i < count[lane]; ++i) {
        value = step(value, i);
        ++executed;
        if (((i + lane) & 1u) != 0u) {
            value ^= 0x13570000u + i;
            if (i == limit)
                break;
            value += 0x24680000u + lane;
        } else {
            value ^= 0x369a0000u + lane;
        }
    }
    out[lane] = uint4(value, executed, count[lane],
                      0xe0000000u | lane);
}

// Continue beneath an observable outer conditional.  This is deliberately
// separate from the simple continue probe, which Metal can if-convert almost
// completely.
kernel void continue_nested_if(device uint4 *out [[buffer(0)]],
                               device const uint *count [[buffer(1)]],
                               device const uint *aux [[buffer(2)]],
                               uint lane [[thread_position_in_grid]])
{
    uint value = aux[lane] ^ 0xf0011223u;
    uint executed = 0, skipped = 0;
    for (uint i = 0; i < count[lane]; ++i) {
        value ^= 0x11110000u + i;
        if (((i ^ lane) & 1u) != 0u) {
            value += 0x22220000u + lane;
            if (((i + aux[lane]) & 3u) == 0u) {
                ++skipped;
                continue;
            }
            value ^= 0x33330000u + i;
        } else {
            value += 0x44440000u + lane;
        }
        value = step(value, i);
        ++executed;
    }
    out[lane] = uint4(value, executed, skipped,
                      0xf0000000u | lane);
}

// The source break is beneath two observable if scopes.  The native form is
// compared against break_nested_if to recover the encoded unwind depth.
kernel void break_nested_two_if(device uint4 *out [[buffer(0)]],
                                device const uint *count [[buffer(1)]],
                                device const uint *aux [[buffer(2)]],
                                uint lane [[thread_position_in_grid]])
{
    uint value = 0x01234567u ^ lane;
    uint executed = 0;
    uint limit = aux[lane] & 31u;
    for (uint i = 0; i < count[lane]; ++i) {
        value = step(value, i);
        ++executed;
        if (((i + lane) & 1u) != 0u) {
            value ^= 0x10200000u + i;
            if (((i ^ lane) & 2u) != 0u) {
                value += 0x20300000u + lane;
                if (i == limit)
                    break;
                value ^= 0x30400000u + i;
            } else {
                value += 0x40500000u + lane;
            }
        } else {
            value ^= 0x50600000u + lane;
        }
    }
    out[lane] = uint4(value, executed, count[lane],
                      0x01000000u | lane);
}

// Three independently dynamic loop scopes exercise the next mask-stack depth
// without creating a large runtime: every per-level bound is at most three.
kernel void triple_nested_loops(device uint4 *out [[buffer(0)]],
                                device const uint *count [[buffer(1)]],
                                device const uint *aux [[buffer(2)]],
                                uint lane [[thread_position_in_grid]])
{
    uint value = 0x12345678u ^ lane;
    uint executed = 0;
    uint outer = min(count[lane], 3u);
    uint middle = aux[lane] & 3u;
    uint inner = (aux[lane] >> 2u) & 3u;
    for (uint i = 0; i < outer; ++i) {
        for (uint j = 0; j < middle; ++j) {
            for (uint k = 0; k < inner; ++k) {
                value = step(value, i * 37u + j * 7u + k);
                ++executed;
            }
            value ^= 0x101u + j;
        }
        value += 0x10001u + i;
    }
    out[lane] = uint4(value, executed, outer,
                      0x02000000u | lane);
}
