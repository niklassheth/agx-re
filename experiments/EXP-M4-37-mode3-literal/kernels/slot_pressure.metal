#include <metal_stdlib>
using namespace metal;

/*
 * Keep N independent device-load results live across a constant-coordinate
 * texture sample.  The source is intentionally unrolled so native instruction
 * order and every mode-3 literal/tail can be inspected directly.
 */

#define ARGS                                                                   \
   texture2d<float> texture [[texture(0)]],                                    \
   sampler texture_sampler [[sampler(0)]],                                     \
   device const float *input [[buffer(0)]],                                    \
   device float4 *output [[buffer(1)]],                                        \
   uint index [[thread_position_in_grid]]

static inline float4 sampled(texture2d<float> texture,
                             sampler texture_sampler)
{
   return texture.sample(texture_sampler, float2(0.125f, 0.625f),
                         level(0.0f));
}

kernel void pressure0(ARGS)
{
   output[index] = sampled(texture, texture_sampler);
}

kernel void pressure1(ARGS)
{
   float a0 = input[index * 8 + 0];
   output[index] = sampled(texture, texture_sampler) + a0;
}

kernel void pressure2(ARGS)
{
   float a0 = input[index * 8 + 0];
   float a1 = input[index * 8 + 1];
   output[index] = sampled(texture, texture_sampler) + a0 + a1 * 2.0f;
}

kernel void pressure3(ARGS)
{
   float a0 = input[index * 8 + 0];
   float a1 = input[index * 8 + 1];
   float a2 = input[index * 8 + 2];
   output[index] = sampled(texture, texture_sampler) + a0 + a1 * 2.0f +
                   a2 * 3.0f;
}

kernel void pressure4(ARGS)
{
   float a0 = input[index * 8 + 0];
   float a1 = input[index * 8 + 1];
   float a2 = input[index * 8 + 2];
   float a3 = input[index * 8 + 3];
   output[index] = sampled(texture, texture_sampler) + a0 + a1 * 2.0f +
                   a2 * 3.0f + a3 * 4.0f;
}

kernel void pressure5(ARGS)
{
   float a0 = input[index * 8 + 0];
   float a1 = input[index * 8 + 1];
   float a2 = input[index * 8 + 2];
   float a3 = input[index * 8 + 3];
   float a4 = input[index * 8 + 4];
   output[index] = sampled(texture, texture_sampler) + a0 + a1 * 2.0f +
                   a2 * 3.0f + a3 * 4.0f + a4 * 5.0f;
}

kernel void pressure6(ARGS)
{
   float a0 = input[index * 8 + 0];
   float a1 = input[index * 8 + 1];
   float a2 = input[index * 8 + 2];
   float a3 = input[index * 8 + 3];
   float a4 = input[index * 8 + 4];
   float a5 = input[index * 8 + 5];
   output[index] = sampled(texture, texture_sampler) + a0 + a1 * 2.0f +
                   a2 * 3.0f + a3 * 4.0f + a4 * 5.0f + a5 * 6.0f;
}

kernel void literal_store(device uint *output [[buffer(0)]],
                          uint index [[thread_position_in_grid]])
{
   output[index] = 0x12345678u;
}

kernel void literal_alu(device const uint *input [[buffer(0)]],
                        device uint2 *output [[buffer(1)]],
                        uint index [[thread_position_in_grid]])
{
   uint value = 0x12345678u;
   output[index] = uint2(value ^ input[index], value + input[index]);
}

kernel void literal_atomic(device atomic_uint *target [[buffer(0)]],
                           device uint *output [[buffer(1)]],
                           uint index [[thread_position_in_grid]])
{
   uint value = 0x12345678u;
   output[index] = atomic_fetch_add_explicit(target, value,
                                              memory_order_relaxed);
}
