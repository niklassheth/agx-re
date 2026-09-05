#include <metal_stdlib>
using namespace metal;
struct Out { float4 position [[position]]; float4 color; float4 second; float4 third; };
vertex Out v_main(uint id [[vertex_id]],
                  constant float4 *a [[buffer(0)]],
                  constant float4 *b [[buffer(1)]],
                  constant float4 *c [[buffer(2)]],
                  constant float4 *d [[buffer(3)]]) {
    Out o;
    o.position = a[id];
    o.color = b[id] * c[id] + d[id];
    o.second = c[id];
    o.third = d[id];
    return o;
}
fragment float4 f_main(Out in [[stage_in]],
                      constant float4 *a [[buffer(0)]],
                      constant float4 *b [[buffer(1)]],
                      constant float4 *c [[buffer(2)]],
                      constant float4 *d [[buffer(3)]]) {
    uint i = uint(in.position.x) & 1;
    return (in.color + in.second * .25 + in.third * .125) * a[i] + b[i] * c[i] + d[i];
}
