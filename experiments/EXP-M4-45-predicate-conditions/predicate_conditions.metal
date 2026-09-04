// Own-source Metal probes for Apple9 predicate comparisons and Boolean
// condition lowering.  Early returns force a real control-flow decision;
// value-only diamonds are intentionally tested separately.
#include <metal_stdlib>
using namespace metal;

#define DIRECT_UINT(NAME, EXPR)                                            \
kernel void NAME(device uint *out [[buffer(0)]],                           \
                 device const uint *a [[buffer(1)]],                       \
                 device const uint *b [[buffer(2)]],                       \
                 uint i [[thread_position_in_grid]])                       \
{                                                                          \
    if (!(EXPR)) return;                                                    \
    out[i] = 0x1000u + i;                                                   \
}

#define DIRECT_INT(NAME, EXPR)                                             \
kernel void NAME(device uint *out [[buffer(0)]],                           \
                 device const int *a [[buffer(1)]],                        \
                 device const int *b [[buffer(2)]],                        \
                 uint i [[thread_position_in_grid]])                       \
{                                                                          \
    if (!(EXPR)) return;                                                    \
    out[i] = 0x2000u + i;                                                   \
}

#define DIRECT_FLOAT(NAME, EXPR)                                           \
kernel void NAME(device uint *out [[buffer(0)]],                           \
                 device const float *a [[buffer(1)]],                      \
                 device const float *b [[buffer(2)]],                      \
                 uint i [[thread_position_in_grid]])                       \
{                                                                          \
    if (!(EXPR)) return;                                                    \
    out[i] = 0x3000u + i;                                                   \
}

DIRECT_UINT(u_lt, a[i] <  b[i])
DIRECT_UINT(u_le, a[i] <= b[i])
DIRECT_UINT(u_gt, a[i] >  b[i])
DIRECT_UINT(u_ge, a[i] >= b[i])
DIRECT_UINT(u_eq, a[i] == b[i])
DIRECT_UINT(u_ne, a[i] != b[i])

DIRECT_INT(s_lt, a[i] <  b[i])
DIRECT_INT(s_le, a[i] <= b[i])
DIRECT_INT(s_gt, a[i] >  b[i])
DIRECT_INT(s_ge, a[i] >= b[i])
DIRECT_INT(s_eq, a[i] == b[i])
DIRECT_INT(s_ne, a[i] != b[i])

DIRECT_FLOAT(f_lt, a[i] <  b[i])
DIRECT_FLOAT(f_le, a[i] <= b[i])
DIRECT_FLOAT(f_gt, a[i] >  b[i])
DIRECT_FLOAT(f_ge, a[i] >= b[i])
DIRECT_FLOAT(f_eq, a[i] == b[i])
DIRECT_FLOAT(f_ne, a[i] != b[i])

#define DIRECT_IMM(NAME, TYPE, EXPR, MARKER)                               \
kernel void NAME(device uint *out [[buffer(0)]],                           \
                 device const TYPE *a [[buffer(1)]],                       \
                 uint i [[thread_position_in_grid]])                       \
{                                                                          \
    if (!(EXPR)) return;                                                    \
    out[i] = (MARKER) + i;                                                  \
}

DIRECT_IMM(u_lt_imm, uint,  a[i] < 17u, 0x6000u)
DIRECT_IMM(u_ge_imm, uint,  a[i] >= 17u, 0x6100u)
DIRECT_IMM(u_eq_imm, uint,  a[i] == 17u, 0x6200u)
DIRECT_IMM(u_ne_imm, uint,  a[i] != 17u, 0x6300u)
DIRECT_IMM(s_lt_imm, int,   a[i] < -7, 0x6400u)
DIRECT_IMM(f_lt_imm, float, a[i] < 0.5f, 0x6500u)

// Liveness variants distinguish comparison polarity from operand retention.
kernel void u_lt_reuse_a(device uint *out [[buffer(0)]],
                         device const uint *a [[buffer(1)]],
                         device const uint *b [[buffer(2)]],
                         uint i [[thread_position_in_grid]])
{
    uint x = a[i], y = b[i];
    if (!(x < y)) return;
    out[i] = x + 0x5000u;
}

kernel void u_lt_reuse_b(device uint *out [[buffer(0)]],
                         device const uint *a [[buffer(1)]],
                         device const uint *b [[buffer(2)]],
                         uint i [[thread_position_in_grid]])
{
    uint x = a[i], y = b[i];
    if (!(x < y)) return;
    out[i] = y + 0x5100u;
}

kernel void u_lt_reuse_both(device uint *out [[buffer(0)]],
                            device const uint *a [[buffer(1)]],
                            device const uint *b [[buffer(2)]],
                            uint i [[thread_position_in_grid]])
{
    uint x = a[i], y = b[i];
    if (!(x < y)) return;
    out[i] = x + y + 0x5200u;
}

kernel void u_eq_reuse_both(device uint *out [[buffer(0)]],
                            device const uint *a [[buffer(1)]],
                            device const uint *b [[buffer(2)]],
                            uint i [[thread_position_in_grid]])
{
    uint x = a[i], y = b[i];
    if (!(x == y)) return;
    out[i] = x + y + 0x5300u;
}

// Compound/derived Boolean conditions.  These retain source-level Boolean
// structure long enough to show whether Metal emits nested control flow,
// combines the comparisons, or materializes a Boolean and compares it.
kernel void bool_bit_test(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          device const uint *b [[buffer(2)]],
                          uint i [[thread_position_in_grid]])
{
    (void)b;
    bool q = (a[i] & 8u) != 0u;
    if (!q) return;
    out[i] = 0x4100u + i;
}

kernel void bool_and(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     device const uint *c [[buffer(3)]],
                     device const uint *d [[buffer(4)]],
                     uint i [[thread_position_in_grid]])
{
    bool q = (a[i] < b[i]) && (c[i] != d[i]);
    if (!q) return;
    out[i] = 0x4200u + i;
}

kernel void bool_or(device uint *out [[buffer(0)]],
                    device const uint *a [[buffer(1)]],
                    device const uint *b [[buffer(2)]],
                    device const uint *c [[buffer(3)]],
                    device const uint *d [[buffer(4)]],
                    uint i [[thread_position_in_grid]])
{
    bool q = (a[i] < b[i]) || (c[i] == d[i]);
    if (!q) return;
    out[i] = 0x4300u + i;
}

kernel void bool_xor(device uint *out [[buffer(0)]],
                     device const uint *a [[buffer(1)]],
                     device const uint *b [[buffer(2)]],
                     device const uint *c [[buffer(3)]],
                     device const uint *d [[buffer(4)]],
                     uint i [[thread_position_in_grid]])
{
    bool q = (a[i] < b[i]) != (c[i] < d[i]);
    if (!q) return;
    out[i] = 0x4400u + i;
}

kernel void bool_selected(device uint *out [[buffer(0)]],
                          device const uint *a [[buffer(1)]],
                          device const uint *b [[buffer(2)]],
                          device const uint *c [[buffer(3)]],
                          device const uint *d [[buffer(4)]],
                          uint i [[thread_position_in_grid]])
{
    bool q = (a[i] & 1u) ? (b[i] < c[i]) : (c[i] == d[i]);
    if (!q) return;
    out[i] = 0x4500u + i;
}

kernel void bool_fanout(device uint *out [[buffer(0)]],
                        device const uint *a [[buffer(1)]],
                        device const uint *b [[buffer(2)]],
                        uint i [[thread_position_in_grid]])
{
    bool q = a[i] < b[i];
    out[i] = q ? 0x4600u + i : 0x4700u + i;
    if (!q) return;
    out[i] ^= 0x00ffu;
}

// Control: the same arbitrary expression in a value-only diamond.  Metal is
// free to use compare/select instead of the execution-mask stack here.
kernel void bool_value_only(device uint *out [[buffer(0)]],
                            device const uint *a [[buffer(1)]],
                            device const uint *b [[buffer(2)]],
                            device const uint *c [[buffer(3)]],
                            device const uint *d [[buffer(4)]],
                            uint i [[thread_position_in_grid]])
{
    bool q = ((a[i] < b[i]) && (c[i] != d[i])) || ((a[i] ^ d[i]) == 7u);
    out[i] = q ? 0x4800u + i : 0x4900u + i;
}

kernel void bool_and_direct(device uint *out [[buffer(0)]],
                            device const uint *a [[buffer(1)]],
                            device const uint *b [[buffer(2)]],
                            device const uint *c [[buffer(3)]],
                            device const uint *d [[buffer(4)]],
                            uint i [[thread_position_in_grid]])
{
    if (!((a[i] < b[i]) && (c[i] != d[i]))) return;
    out[i] = 0x4a00u + i;
}

kernel void bool_or_direct(device uint *out [[buffer(0)]],
                           device const uint *a [[buffer(1)]],
                           device const uint *b [[buffer(2)]],
                           device const uint *c [[buffer(3)]],
                           device const uint *d [[buffer(4)]],
                           uint i [[thread_position_in_grid]])
{
    if (!((a[i] < b[i]) || (c[i] == d[i]))) return;
    out[i] = 0x4b00u + i;
}

kernel void bool_arith_nonzero(device uint *out [[buffer(0)]],
                               device const uint *a [[buffer(1)]],
                               device const uint *b [[buffer(2)]],
                               device const uint *c [[buffer(3)]],
                               uint i [[thread_position_in_grid]])
{
    uint x = (a[i] * 3u + b[i]) ^ c[i];
    if (x == 0u) return;
    out[i] = 0x4c00u + i;
}

kernel void bool_fanout_side_effect(device uint *out [[buffer(0)]],
                                    device const uint *a [[buffer(1)]],
                                    device const uint *b [[buffer(2)]],
                                    device uint *bool_out [[buffer(3)]],
                                    uint i [[thread_position_in_grid]])
{
    bool q = a[i] < b[i];
    bool_out[i] = uint(q);
    if (!q) return;
    out[i] = 0x4d00u + i;
}
