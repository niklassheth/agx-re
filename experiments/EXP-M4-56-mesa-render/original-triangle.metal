#include <metal_stdlib>
using namespace metal;
struct Out { float4 position [[position]]; float3 color; };
vertex Out triangle_vertex(uint id [[vertex_id]]) {
    const float2 positions[3] = {
        float2( 0.0,  0.82),
        float2(-0.82, -0.72),
        float2( 0.82, -0.72)
    };
    const float3 colors[3] = {
        float3(1.0, 0.15, 0.10),
        float3(0.10, 1.0, 0.20),
        float3(0.15, 0.30, 1.0)
    };
    Out out;
    out.position = float4(positions[id], 0.0, 1.0);
    out.color = colors[id];
    return out;
}
fragment float4 triangle_fragment(Out in [[stage_in]]) {
    return float4(in.color, 1.0);
}
