#include <metal_stdlib>

using namespace metal;

kernel void rcp_bfloat_store(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=1.0f/x; saved[gid]=bias[gid];
}

kernel void rcp_bfloat_reuse(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=1.0f/x; saved[gid]=x+bias[gid];
}

kernel void rsqrt_bfloat_store(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=rsqrt(x); saved[gid]=bias[gid];
}

kernel void rsqrt_bfloat_reuse(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=rsqrt(x); saved[gid]=x+bias[gid];
}

kernel void exp2_bfloat_store(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=exp2(x); saved[gid]=bias[gid];
}

kernel void exp2_bfloat_reuse(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=exp2(x); saved[gid]=x+bias[gid];
}

kernel void log2_bfloat_store(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=log2(x); saved[gid]=bias[gid];
}

kernel void log2_bfloat_reuse(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=log2(x); saved[gid]=x+bias[gid];
}

kernel void floor_bfloat_store(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=floor(x); saved[gid]=bias[gid];
}

kernel void floor_bfloat_reuse(device const bfloat *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=floor(x); saved[gid]=x+bias[gid];
}

kernel void rcp_half_store(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=1.0f/x; saved[gid]=bias[gid];
}

kernel void rcp_half_reuse(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=1.0f/x; saved[gid]=x+bias[gid];
}

kernel void rsqrt_half_store(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=rsqrt(x); saved[gid]=bias[gid];
}

kernel void rsqrt_half_reuse(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=rsqrt(x); saved[gid]=x+bias[gid];
}

kernel void exp2_half_store(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=exp2(x); saved[gid]=bias[gid];
}

kernel void exp2_half_reuse(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=exp2(x); saved[gid]=x+bias[gid];
}

kernel void log2_half_store(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=log2(x); saved[gid]=bias[gid];
}

kernel void log2_half_reuse(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=log2(x); saved[gid]=x+bias[gid];
}

kernel void floor_half_store(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=floor(x); saved[gid]=bias[gid];
}

kernel void floor_half_reuse(device const half *input [[buffer(0)]], device const float *bias [[buffer(1)]], device float *out [[buffer(2)]], device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=float(input[gid]); out[gid]=floor(x); saved[gid]=x+bias[gid];
}
