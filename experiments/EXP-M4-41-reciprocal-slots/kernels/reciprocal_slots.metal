#include <metal_stdlib>
using namespace metal;

kernel void rcp_store(device const float *in [[buffer(0)]],
                      device float *out [[buffer(1)]],
                      uint gid [[thread_position_in_grid]])
{
   float x = in[gid];
   out[gid] = 1.0f / x;
}

kernel void rcp_result_alu(device const float *in [[buffer(0)]],
                           device const float *scale [[buffer(1)]],
                           device float *out [[buffer(2)]],
                           uint gid [[thread_position_in_grid]])
{
   float x = in[gid];
   float y = 1.0f / x;
   out[gid] = y * scale[gid];
}

kernel void rcp_source_reuse(device const float *in [[buffer(0)]],
                             device const float *add [[buffer(1)]],
                             device float *reciprocal_out [[buffer(2)]],
                             device float *source_out [[buffer(3)]],
                             uint gid [[thread_position_in_grid]])
{
   float x = in[gid];
   float y = 1.0f / x;
   reciprocal_out[gid] = y;
   source_out[gid] = x + add[gid];
}

kernel void rcp_after_alu(device const float *in [[buffer(0)]],
                          device const float *bias [[buffer(1)]],
                          device float *out [[buffer(2)]],
                          uint gid [[thread_position_in_grid]])
{
   float x = in[gid] + bias[gid];
   out[gid] = 1.0f / x;
}

kernel void rcp_after_alu_with_pending(
   device const float *a [[buffer(0)]],
   device const float *b [[buffer(1)]],
   device const float *c [[buffer(2)]],
   device const float *d [[buffer(3)]],
   device float *reciprocal_out [[buffer(4)]],
   device float *pending_out [[buffer(5)]],
   uint gid [[thread_position_in_grid]])
{
   float x = a[gid] + b[gid];
   float pending = c[gid] + d[gid];
   reciprocal_out[gid] = 1.0f / x;
   pending_out[gid] = pending;
}

kernel void rcp_result_fanout(device const float *in [[buffer(0)]],
                              device const float *a [[buffer(1)]],
                              device const float *b [[buffer(2)]],
                              device float *out0 [[buffer(3)]],
                              device float *out1 [[buffer(4)]],
                              uint gid [[thread_position_in_grid]])
{
   float y = 1.0f / in[gid];
   out0[gid] = y * a[gid];
   out1[gid] = y + b[gid];
}

kernel void rcp_source_and_result_fanout(
   device const float *in [[buffer(0)]],
   device const float *a [[buffer(1)]],
   device const float *b [[buffer(2)]],
   device float *out0 [[buffer(3)]],
   device float *out1 [[buffer(4)]],
   device float *out2 [[buffer(5)]],
   uint gid [[thread_position_in_grid]])
{
   float x = in[gid];
   float y = 1.0f / x;
   out0[gid] = y * a[gid];
   out1[gid] = y + b[gid];
   out2[gid] = x - b[gid];
}

kernel void rcp_float4(device const float4 *in [[buffer(0)]],
                       device float4 *out [[buffer(1)]],
                       uint gid [[thread_position_in_grid]])
{
   float4 x = in[gid];
   out[gid] = 1.0f / x;
}

kernel void rcp_eight_live(device const float *in [[buffer(0)]],
                           device const float *scale [[buffer(1)]],
                           device float *out [[buffer(2)]],
                           uint gid [[thread_position_in_grid]])
{
   float x0 = 1.0f / in[gid * 8 + 0];
   float x1 = 1.0f / in[gid * 8 + 1];
   float x2 = 1.0f / in[gid * 8 + 2];
   float x3 = 1.0f / in[gid * 8 + 3];
   float x4 = 1.0f / in[gid * 8 + 4];
   float x5 = 1.0f / in[gid * 8 + 5];
   float x6 = 1.0f / in[gid * 8 + 6];
   float x7 = 1.0f / in[gid * 8 + 7];
   float s = scale[gid];
   out[gid * 8 + 0] = x0 * s;
   out[gid * 8 + 1] = x1 * s;
   out[gid * 8 + 2] = x2 * s;
   out[gid * 8 + 3] = x3 * s;
   out[gid * 8 + 4] = x4 * s;
   out[gid * 8 + 5] = x5 * s;
   out[gid * 8 + 6] = x6 * s;
   out[gid * 8 + 7] = x7 * s;
}
