#include <metal_stdlib>

using namespace metal;

kernel void rcp_float_store(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=float(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_float_reuse(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=float(1)/x;
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void rcp_float_alu(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = x + bias[gid];
 float y=float(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_float_neg(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = -x;
 float y=float(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_float_abs(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = abs(x);
 float y=float(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_float_store(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_float_reuse(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=rsqrt(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void rsqrt_float_alu(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = x + bias[gid];
 float y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_float_neg(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = -x;
 float y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_float_abs(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = abs(x);
 float y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_float_store(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_float_reuse(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=exp2(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void exp2_float_alu(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = x + bias[gid];
 float y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_float_neg(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = -x;
 float y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_float_abs(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = abs(x);
 float y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_float_store(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_float_reuse(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=log2(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void log2_float_alu(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = x + bias[gid];
 float y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_float_neg(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = -x;
 float y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_float_abs(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = abs(x);
 float y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_float_store(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_float_reuse(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; 
 float y=floor(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void floor_float_alu(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = x + bias[gid];
 float y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_float_neg(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = -x;
 float y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_float_abs(device const float *input [[buffer(0)]],
 device const float *bias [[buffer(1)]], device float *out [[buffer(2)]],
 device float *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 float x=input[gid]; x = abs(x);
 float y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_half_store(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=half(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_half_reuse(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=half(1)/x;
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void rcp_half_alu(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = x + bias[gid];
 half y=half(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_half_neg(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = -x;
 half y=half(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rcp_half_abs(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = abs(x);
 half y=half(1)/x;
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_half_store(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_half_reuse(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=rsqrt(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void rsqrt_half_alu(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = x + bias[gid];
 half y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_half_neg(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = -x;
 half y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void rsqrt_half_abs(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = abs(x);
 half y=rsqrt(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_half_store(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_half_reuse(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=exp2(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void exp2_half_alu(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = x + bias[gid];
 half y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_half_neg(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = -x;
 half y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void exp2_half_abs(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = abs(x);
 half y=exp2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_half_store(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_half_reuse(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=log2(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void log2_half_alu(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = x + bias[gid];
 half y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_half_neg(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = -x;
 half y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void log2_half_abs(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = abs(x);
 half y=log2(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_half_store(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_half_reuse(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; 
 half y=floor(x);
 out[gid]=y;
 saved[gid]=x + bias[gid];
}

kernel void floor_half_alu(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = x + bias[gid];
 half y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_half_neg(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = -x;
 half y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}

kernel void floor_half_abs(device const half *input [[buffer(0)]],
 device const half *bias [[buffer(1)]], device half *out [[buffer(2)]],
 device half *saved [[buffer(3)]], uint gid [[thread_position_in_grid]]) {
 half x=input[gid]; x = abs(x);
 half y=floor(x);
 out[gid]=y;
 saved[gid]=bias[gid];
}
