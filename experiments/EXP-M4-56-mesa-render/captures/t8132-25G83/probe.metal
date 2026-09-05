#include <metal_stdlib>
using namespace metal;
struct VOut { float4 position [[position]]; float3 color; };
vertex VOut v_main(uint id [[vertex_id]]) {
    VOut o;
    o.position = float4(id == 0 ? -0.75f : (id == 1 ? 0.75f : 0.0f),
                        id == 2 ? 0.75f : -0.75f, 0.0f, 1.0f);
    o.color = float3(id == 0 ? 1.0f : 0.0f, id == 1 ? 1.0f : 0.0f,
                     id == 2 ? 1.0f : 0.0f);
    #pragma clang loop unroll(full)
    for (uint i = 0; i < 128; ++i)
        o.position.x = fma(o.position.x, 1.000001f, 0.000001f);
    return o;
}
fragment float4 f_main(VOut in [[stage_in]]) {
    float3 a = in.color * in.color + float3(0.1f, 0.2f, 0.3f);
    float3 b = a * in.color + float3(0.01f, 0.02f, 0.03f);
    #pragma clang loop unroll(full)
    for (uint i = 0; i < 128; ++i)
        b.x = fma(b.x, 1.000001f, 0.000001f);
    return float4(b * b, 1.0f);
}
