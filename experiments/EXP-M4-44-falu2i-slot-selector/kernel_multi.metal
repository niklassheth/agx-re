#include <metal_stdlib>
using namespace metal;

kernel void falu2i_six_loads(device float *out [[buffer(0)]],
                             device const float *a [[buffer(1)]],
                             device const float *b [[buffer(2)]],
                             device const float *c [[buffer(3)]],
                             device const float *d [[buffer(4)]],
                             device const float *e [[buffer(5)]],
                             device const float *f [[buffer(6)]],
                             uint i [[thread_position_in_grid]])
{
    float va = a[i];
    float vb = b[i];
    float vc = c[i];
    float vd = d[i];
    float ve = e[i];
    float vf = f[i];

    uint base = i * 8u;
    out[base + 0u] = va + 1.5f;
    out[base + 1u] = vb + 2.5f;
    out[base + 2u] = vc + 3.5f;
    out[base + 3u] = vd + 4.5f;
    out[base + 4u] = ve + 5.5f;
    out[base + 5u] = vf + 6.5f;
}
