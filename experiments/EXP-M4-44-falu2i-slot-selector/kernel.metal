#include <metal_stdlib>
using namespace metal;

kernel void falu2i_slot_cross(device float *out [[buffer(0)]],
                              device const float *in [[buffer(1)]],
                              uint i [[thread_position_in_grid]])
{
    out[i] = in[i] + 1.5f;
}
