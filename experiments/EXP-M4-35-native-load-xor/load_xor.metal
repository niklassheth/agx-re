#include <metal_stdlib>
using namespace metal;

kernel void alu_xor_alu(
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint first = idx * 0x01010101u + 0x10203040u;
    uint second = idx * 0x11111111u + 0x76543210u;
    out[idx] = first ^ second;
}

kernel void load_xor_gid(
    device const uint *in0 [[buffer(0)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint value = in0[(idx * 3u + 1u) & 1023u];
    uint partner = idx * 0x01010101u + 0x10203040u;
    out[idx] = value ^ partner;
}

kernel void materialized_xor(
    device const uint *in0 [[buffer(0)]],
    device const uint *in1 [[buffer(1)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    float first = as_type<float>(in0[idx & 1023u]) * 1.5f;
    float second = as_type<float>(in1[(idx + 37u) & 1023u]) * 2.5f;
    out[idx] = as_type<uint>(first) ^ as_type<uint>(second);
}

kernel void load_xor_load_distinct(
    device const uint *in0 [[buffer(0)]],
    device const uint *in1 [[buffer(1)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint first = in0[idx & 1023u];
    uint second = in1[(idx + 37u) & 1023u];
    out[idx] = first ^ second;
}

kernel void load_xor_load_same(
    device const uint *in0 [[buffer(0)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint first = in0[idx & 1023u];
    uint second = in0[(idx + 37u) & 1023u];
    out[idx] = first ^ second;
}

kernel void load_xor_load_retain(
    device const uint *in0 [[buffer(0)]],
    device const uint *in1 [[buffer(1)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint first = in0[idx & 1023u];
    uint second = in1[(idx + 37u) & 1023u];
    out[idx] = first ^ second;
    out[idx + 64u] = first + second;
}

kernel void load_xor_chain5(
    device const uint *in0 [[buffer(0)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint p0 = in0[(idx + 0u) & 1023u];
    uint p1 = in0[(idx + 37u) & 1023u];
    uint p2 = in0[(idx + 74u) & 1023u];
    uint p3 = in0[(idx + 111u) & 1023u];
    uint p4 = in0[(idx + 148u) & 1023u];
    uint q0 = p0 ^ (idx + 0x10203040u);
    uint q1 = p1 ^ (idx + 0x21314151u);
    uint q2 = p2 ^ (idx + 0x32425262u);
    uint q3 = p3 ^ (idx + 0x43536373u);
    uint q4 = p4 ^ (idx + 0x54647484u);
    out[idx + 0u] = q0;
    out[idx + 64u] = q1;
    out[idx + 128u] = q2;
    out[idx + 192u] = q3;
    out[idx + 256u] = q4;
}

kernel void load_xor_chain6(
    device const uint *in0 [[buffer(0)]],
    device uint *out [[buffer(3)]],
    uint idx [[thread_position_in_grid]])
{
    uint p0 = in0[(idx + 0u) & 1023u];
    uint p1 = in0[(idx + 37u) & 1023u];
    uint p2 = in0[(idx + 74u) & 1023u];
    uint p3 = in0[(idx + 111u) & 1023u];
    uint p4 = in0[(idx + 148u) & 1023u];
    uint p5 = in0[(idx + 185u) & 1023u];
    uint q0 = p0 ^ (idx + 0x10203040u);
    uint q1 = p1 ^ (idx + 0x21314151u);
    uint q2 = p2 ^ (idx + 0x32425262u);
    uint q3 = p3 ^ (idx + 0x43536373u);
    uint q4 = p4 ^ (idx + 0x54647484u);
    uint q5 = p5 ^ (idx + 0x65758595u);
    out[idx + 0u] = q0;
    out[idx + 64u] = q1;
    out[idx + 128u] = q2;
    out[idx + 192u] = q3;
    out[idx + 256u] = q4;
    out[idx + 320u] = q5;
}
