#include <metal_stdlib>
using namespace metal;

/*
 * Keep every literal outside the compact seven-bit range while changing one
 * source bit at a time.  XORing a common dense base avoids giving Metal a
 * qualitatively different constant-lowering opportunity for any bit.
 */
#define LITERAL_KERNEL(name, value)                                            \
   kernel void name(device uint *output [[buffer(0)]],                         \
                    uint index [[thread_position_in_grid]])                    \
   {                                                                           \
      output[index] = value;                                                   \
}
#define BASE 0x5a5aa5a5u

LITERAL_KERNEL(literal_base, BASE)
LITERAL_KERNEL(literal_b00, BASE ^ (1u << 0))
LITERAL_KERNEL(literal_b01, BASE ^ (1u << 1))
LITERAL_KERNEL(literal_b02, BASE ^ (1u << 2))
LITERAL_KERNEL(literal_b03, BASE ^ (1u << 3))
LITERAL_KERNEL(literal_b04, BASE ^ (1u << 4))
LITERAL_KERNEL(literal_b05, BASE ^ (1u << 5))
LITERAL_KERNEL(literal_b06, BASE ^ (1u << 6))
LITERAL_KERNEL(literal_b07, BASE ^ (1u << 7))
LITERAL_KERNEL(literal_b08, BASE ^ (1u << 8))
LITERAL_KERNEL(literal_b09, BASE ^ (1u << 9))
LITERAL_KERNEL(literal_b10, BASE ^ (1u << 10))
LITERAL_KERNEL(literal_b11, BASE ^ (1u << 11))
LITERAL_KERNEL(literal_b12, BASE ^ (1u << 12))
LITERAL_KERNEL(literal_b13, BASE ^ (1u << 13))
LITERAL_KERNEL(literal_b14, BASE ^ (1u << 14))
LITERAL_KERNEL(literal_b15, BASE ^ (1u << 15))
LITERAL_KERNEL(literal_b16, BASE ^ (1u << 16))
LITERAL_KERNEL(literal_b17, BASE ^ (1u << 17))
LITERAL_KERNEL(literal_b18, BASE ^ (1u << 18))
LITERAL_KERNEL(literal_b19, BASE ^ (1u << 19))
LITERAL_KERNEL(literal_b20, BASE ^ (1u << 20))
LITERAL_KERNEL(literal_b21, BASE ^ (1u << 21))
LITERAL_KERNEL(literal_b22, BASE ^ (1u << 22))
LITERAL_KERNEL(literal_b23, BASE ^ (1u << 23))
LITERAL_KERNEL(literal_b24, BASE ^ (1u << 24))
LITERAL_KERNEL(literal_b25, BASE ^ (1u << 25))
LITERAL_KERNEL(literal_b26, BASE ^ (1u << 26))
LITERAL_KERNEL(literal_b27, BASE ^ (1u << 27))
LITERAL_KERNEL(literal_b28, BASE ^ (1u << 28))
LITERAL_KERNEL(literal_b29, BASE ^ (1u << 29))
LITERAL_KERNEL(literal_b30, BASE ^ (1u << 30))
LITERAL_KERNEL(literal_b31, BASE ^ (1u << 31))
