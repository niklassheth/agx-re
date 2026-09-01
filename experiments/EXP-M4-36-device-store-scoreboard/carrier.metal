// Own-source carrier for EXP-M4-36.  The experiment replaces the complete
// _agc.main body; this source supplies only the public buffer ABI and archive
// identity.  It deliberately matches the proven low-pressure EXP-0141 shape.
#include <metal_stdlib>
using namespace metal;

kernel void k(device uint *out [[buffer(0)]],
              device const uint *mem [[buffer(1)]],
              uint tid [[thread_position_in_grid]])
{
    uint a0 = mem[tid + 0];
    uint a1 = mem[tid + 1];
    uint a2 = mem[tid + 2];
    uint a3 = mem[tid + 3];
    out[tid + 0] = a0 + a1;
    out[tid + 1] = a2 ^ a3;
    out[tid + 2] = a0 * a2;
    out[tid + 3] = a1 | a3;
}
