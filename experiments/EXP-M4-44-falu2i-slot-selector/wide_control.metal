#include <metal_stdlib>
using namespace metal;

kernel void u2f_slot_control(device float *out [[buffer(0)]],
                             device const uint *in [[buffer(1)]],
                             uint i [[thread_position_in_grid]])
{
    out[i] = float(in[i]);
}
