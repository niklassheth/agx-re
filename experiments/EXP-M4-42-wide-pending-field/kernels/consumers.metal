#include <metal_stdlib>
using namespace metal;

kernel void u2f_load(device float *out [[buffer(0)]],
                     device const uint *in [[buffer(1)]],
                     uint i [[thread_position_in_grid]])
{
    out[i] = float(in[i]);
}

kernel void i2f_load(device float *out [[buffer(0)]],
                     device const int *in [[buffer(1)]],
                     uint i [[thread_position_in_grid]])
{
    out[i] = float(in[i]);
}

kernel void f2u_load(device uint *out [[buffer(0)]],
                     device const float *in [[buffer(1)]],
                     uint i [[thread_position_in_grid]])
{
    out[i] = uint(in[i]);
}

kernel void reciprocal_load(device float *out [[buffer(0)]],
                            device const float *in [[buffer(1)]],
                            uint i [[thread_position_in_grid]])
{
    out[i] = 1.0f / in[i];
}

kernel void popcount_load(device uint *out [[buffer(0)]],
                          device const uint *in [[buffer(1)]],
                          uint i [[thread_position_in_grid]])
{
    out[i] = popcount(in[i]);
}

kernel void clz_load(device uint *out [[buffer(0)]],
                     device const uint *in [[buffer(1)]],
                     uint i [[thread_position_in_grid]])
{
    out[i] = clz(in[i]);
}

kernel void shift_load(device uint *out [[buffer(0)]],
                       device const uint *in [[buffer(1)]],
                       uint i [[thread_position_in_grid]])
{
    out[i] = in[i] >> 5u;
}

kernel void imad_load(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      device const uint *c [[buffer(3)]],
                      uint i [[thread_position_in_grid]])
{
    out[i] = a[i] * b[i] + c[i];
}

kernel void extract_load(device uint *out [[buffer(0)]],
                         device const uint *in [[buffer(1)]],
                         uint i [[thread_position_in_grid]])
{
    out[i] = extract_bits(in[i], 5u, 11u);
}

kernel void insert_load(device uint *out [[buffer(0)]],
                        device const uint *base [[buffer(1)]],
                        device const uint *bits [[buffer(2)]],
                        uint i [[thread_position_in_grid]])
{
    out[i] = insert_bits(base[i], bits[i], 7u, 9u);
}

kernel void sys_u2f(device float *out [[buffer(0)]],
                    uint i [[thread_position_in_grid]])
{
    out[i] = float(i);
}

kernel void sys_iadd(device uint *out [[buffer(0)]],
                     uint i [[thread_position_in_grid]])
{
    out[i] = i + 0x1234u;
}

kernel void iadd_load(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint i [[thread_position_in_grid]])
{
    out[i] = a[i] + b[i];
}

kernel void isub_load(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint i [[thread_position_in_grid]])
{
    out[i] = a[i] - b[i];
}

kernel void umin_load(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint i [[thread_position_in_grid]])
{
    out[i] = min(a[i], b[i]);
}

kernel void umax_load(device uint *out [[buffer(0)]],
                      device const uint *a [[buffer(1)]],
                      device const uint *b [[buffer(2)]],
                      uint i [[thread_position_in_grid]])
{
    out[i] = max(a[i], b[i]);
}

kernel void shift_dynamic_load(device uint *out [[buffer(0)]],
                               device const uint *value [[buffer(1)]],
                               device const uint *amount [[buffer(2)]],
                               uint i [[thread_position_in_grid]])
{
    out[i] = value[i] >> (amount[i] & 31u);
}

kernel void asr_dynamic_load(device int *out [[buffer(0)]],
                             device const int *value [[buffer(1)]],
                             device const uint *amount [[buffer(2)]],
                             uint i [[thread_position_in_grid]])
{
    out[i] = value[i] >> (amount[i] & 31u);
}

kernel void rotate_dynamic_load(device uint *out [[buffer(0)]],
                                device const uint *value [[buffer(1)]],
                                device const uint *amount [[buffer(2)]],
                                uint i [[thread_position_in_grid]])
{
    out[i] = rotate(value[i], amount[i] & 31u);
}

kernel void reverse_load(device uint *out [[buffer(0)]],
                         device const uint *value [[buffer(1)]],
                         uint i [[thread_position_in_grid]])
{
    out[i] = reverse_bits(value[i]);
}

kernel void sys_three(device uint *out [[buffer(0)]],
                      uint gid [[thread_position_in_grid]],
                      uint lid [[thread_position_in_threadgroup]],
                      uint group [[threadgroup_position_in_grid]])
{
    uint base = gid * 3u;
    out[base + 0u] = as_type<uint>(float(gid));
    out[base + 1u] = as_type<uint>(float(lid));
    out[base + 2u] = as_type<uint>(float(group));
}
