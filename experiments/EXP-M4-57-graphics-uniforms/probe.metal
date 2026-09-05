#include <metal_stdlib>
using namespace metal;
struct Out { float4 position [[position]]; float3 color; };
vertex Out v_main(uint id [[vertex_id]], constant float4 *data [[buffer(0)]]) {
    Out o;
    float x = id == 0 ? -0.75 : (id == 1 ? 0.75 : 0.0);
    float y = id == 2 ? 0.75 : -0.75;
    o.position = float4(x, y, 0, 1);
    o.color = data[id].xyz;
    return o;
}
fragment float4 f_main(Out in [[stage_in]], constant float4 *data [[buffer(0)]]) {
    return float4(in.color * data[uint(in.position.x) & 1].xyz, 1);
}
