#include <metal_stdlib>
using namespace metal;

/*
 * Own-source probes for the Apple9 extended 32-bit literal form.  These
 * constants are deliberately consumed by texture operations, where Metal's
 * compiler retains the literal construction instead of folding it away.
 */

kernel void sample_const(texture2d<float> texture [[texture(0)]],
                         sampler texture_sampler [[sampler(0)]],
                         device float4 *output [[buffer(0)]],
                         uint index [[thread_position_in_grid]])
{
   output[index] = texture.sample(texture_sampler, float2(0.125f, 0.625f),
                                  level(0.0f));
}

kernel void sample_const_alt(texture2d<float> texture [[texture(0)]],
                             sampler texture_sampler [[sampler(0)]],
                             device float4 *output [[buffer(0)]],
                             uint index [[thread_position_in_grid]])
{
   output[index] = texture.sample(texture_sampler, float2(0.375f, 0.875f),
                                  level(0.0f));
}

kernel void write_const(texture2d<float, access::write> texture [[texture(0)]],
                        uint index [[thread_position_in_grid]])
{
   uint2 coordinate = uint2(index & 3, index >> 2);
   texture.write(float4(0.125f, 0.375f, 0.625f, 0.875f), coordinate);
}

struct VertexOutput {
   float4 position [[position]];
   float2 coordinate;
};

vertex VertexOutput vertex_mode3(uint vertex_id [[vertex_id]])
{
   float2 corner = float2((vertex_id << 1) & 2, vertex_id & 2);
   VertexOutput output;
   output.position = float4(corner * 2.0f - 1.0f, 0.375f, 1.0f);
   output.coordinate = corner * float2(0.125f, 0.375f) +
                       float2(0.125f, 0.125f);
   return output;
}

fragment float4 fragment_mode3(VertexOutput input [[stage_in]])
{
   return float4(input.coordinate, 0.625f, 1.0f);
}

struct PressureVertexOutput {
   float4 position [[position]];
   float4 value0;
   float4 value1;
   float4 value2;
   float4 value3;
   float4 value4;
};

vertex PressureVertexOutput vertex_literal_pressure(uint vertex_id [[vertex_id]])
{
   float2 corner = float2((vertex_id << 1) & 2, vertex_id & 2);
   PressureVertexOutput output;
   output.position = float4(corner * 2.0f - 1.0f, 0.375f, 1.0f);
   output.value0 = float4(0.125f, 0.375f, 0.625f, 0.875f);
   output.value1 = float4(1.125f, 1.375f, 1.625f, 1.875f);
   output.value2 = float4(2.125f, 2.375f, 2.625f, 2.875f);
   output.value3 = float4(3.125f, 3.375f, 3.625f, 3.875f);
   output.value4 = float4(4.125f, 4.375f, 4.625f, 4.875f);
   return output;
}

fragment float4 fragment_literal_pressure(PressureVertexOutput input [[stage_in]])
{
   return fract(input.value0 * 0.03125f + input.value1 * 0.0625f +
                input.value2 * 0.125f + input.value3 * 0.25f +
                input.value4 * 0.5f);
}
