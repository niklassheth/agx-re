#include <metal_stdlib>

using namespace metal;

kernel void k_rsqrt(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=fast::rsqrt(x); }

kernel void k_sqrt(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=fast::sqrt(x); }

kernel void k_sqrt_precise(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=precise::sqrt(x); }

kernel void k_sin(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=sin(x); }

kernel void k_sin_fast(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=fast::sin(x); }

kernel void k_sinpi(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=sinpi(x); }

kernel void k_cos(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=cos(x); }

kernel void k_cospi(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=cospi(x); }

kernel void k_tan(device const float *input [[buffer(0)]], device float *out [[buffer(1)]], uint gid [[thread_position_in_grid]]) { float x=input[gid];out[gid]=tan(x); }
