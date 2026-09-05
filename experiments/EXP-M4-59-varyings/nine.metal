#include <metal_stdlib>
using namespace metal;
struct Out { float4 position [[position]]; float3 color; float3 second; float3 third; };
vertex Out v_main(uint id [[vertex_id]],
                  constant float4 *a [[buffer(0)]],
                  constant float4 *b [[buffer(1)]],
                  constant float4 *c [[buffer(2)]],
                  constant float4 *d [[buffer(3)]]) {
    Out o;
    o.position = a[id];
    o.color = b[id].xyz * c[id].xyz + d[id].xyz;
    o.second = c[id].xyz;
    o.third = d[id].xyz;
    return o;
}
fragment float4 f_main(Out in [[stage_in]],
                      constant float4 *a [[buffer(0)]],
                      constant float4 *b [[buffer(1)]],
                      constant float4 *c [[buffer(2)]],
                      constant float4 *d [[buffer(3)]]) {
    uint i = uint(in.position.x) & 1;
    return float4((in.color + in.second * .25 + in.third * .125) * a[i].xyz + b[i].xyz * c[i].xyz + d[i].xyz, 1);
}
