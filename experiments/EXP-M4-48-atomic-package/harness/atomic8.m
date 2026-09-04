// SPDX-License-Identifier: MIT
// Own-source T8132 Metal harness matching Mesa's eight-resource carrier shape.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

enum { COUNT = 64, LOCAL = 16, INPUTS = 6, TARGET = 6, OUTPUT = 7 };

typedef struct {
   uint32_t old_value;
   uint32_t new_value;
   uint32_t operand;
   uint32_t witness;
} Result;

static const char *source =
   "#include <metal_stdlib>\n"
   "using namespace metal;\n"
   "struct Result { uint old_value, new_value, operand, witness; };\n"
   "kernel void atomic8(device const uint *in0 [[buffer(0)]],\n"
   "                    device const uint *in1 [[buffer(1)]],\n"
   "                    device const uint *in2 [[buffer(2)]],\n"
   "                    device const uint *in3 [[buffer(3)]],\n"
   "                    device const uint *in4 [[buffer(4)]],\n"
   "                    device const uint *in5 [[buffer(5)]],\n"
   "                    device atomic_uint *target [[buffer(6)]],\n"
   "                    device Result *out [[buffer(7)]],\n"
   "                    uint gid [[thread_position_in_grid]]) {\n"
   "  uint operand = ((in0[gid] + in1[gid]) ^ in2[gid]) +\n"
   "                 ((in3[gid] & in4[gid]) | in5[gid]);\n"
   "  uint old_value = atomic_fetch_add_explicit(&target[gid], operand,\n"
   "                                               memory_order_relaxed);\n"
   "  uint new_value = atomic_load_explicit(&target[gid],\n"
   "                                          memory_order_relaxed);\n"
   "  out[gid] = { old_value, new_value, operand, gid ^ 0xa917c0deu };\n"
   "}\n";

static uint32_t
input_value(unsigned slot, unsigned i)
{
   return (0x1020304u * (slot + 1)) ^ (i * (0x10101u + slot * 0x111u));
}

static uint32_t
operand_value(unsigned i)
{
   uint32_t v[INPUTS];
   for (unsigned slot = 0; slot < INPUTS; ++slot)
      v[slot] = input_value(slot, i);
   return ((v[0] + v[1]) ^ v[2]) + ((v[3] & v[4]) | v[5]);
}

int
main(void)
{
   @autoreleasepool {
      id<MTLDevice> device = MTLCreateSystemDefaultDevice();
      if (!device) {
         fprintf(stderr, "no Metal device\n");
         return 1;
      }

      NSError *error = nil;
      id<MTLLibrary> library =
         [device newLibraryWithSource:[NSString stringWithUTF8String:source]
                              options:nil
                                error:&error];
      if (!library) {
         fprintf(stderr, "compile failed: %s\n",
                 [[error localizedDescription] UTF8String]);
         return 1;
      }
      id<MTLFunction> function = [library newFunctionWithName:@"atomic8"];
      id<MTLComputePipelineState> pipeline =
         [device newComputePipelineStateWithFunction:function error:&error];
      if (!pipeline) {
         fprintf(stderr, "pipeline failed: %s\n",
                 [[error localizedDescription] UTF8String]);
         return 1;
      }

      id<MTLBuffer> buffers[8] = {nil};
      for (unsigned slot = 0; slot < INPUTS; ++slot) {
         buffers[slot] =
            [device newBufferWithLength:COUNT * sizeof(uint32_t)
                                options:MTLResourceStorageModeShared];
         uint32_t *words = [buffers[slot] contents];
         for (unsigned i = 0; i < COUNT; ++i)
            words[i] = input_value(slot, i);
      }
      buffers[TARGET] =
         [device newBufferWithLength:COUNT * sizeof(uint32_t)
                             options:MTLResourceStorageModeShared];
      buffers[OUTPUT] =
         [device newBufferWithLength:COUNT * sizeof(Result)
                             options:MTLResourceStorageModeShared];
      uint32_t *target = [buffers[TARGET] contents];
      Result *output = [buffers[OUTPUT] contents];
      for (unsigned i = 0; i < COUNT; ++i)
         target[i] = 0x60000000u + 17u * i;
      memset(output, 0, COUNT * sizeof(*output));

      printf("CASE grid=%ux1x1 local=%ux1x1\n", COUNT, LOCAL);
      for (unsigned slot = 0; slot < 8; ++slot)
         printf("BUFFER slot=%u address=%#018" PRIx64 " size=%lu\n", slot,
                (uint64_t)[buffers[slot] gpuAddress],
                (unsigned long)[buffers[slot] length]);
      fflush(stdout);

      id<MTLCommandQueue> queue = [device newCommandQueue];
      id<MTLCommandBuffer> command = [queue commandBuffer];
      id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
      [encoder setComputePipelineState:pipeline];
      for (unsigned slot = 0; slot < 8; ++slot)
         [encoder setBuffer:buffers[slot] offset:0 atIndex:slot];
      [encoder dispatchThreads:MTLSizeMake(COUNT, 1, 1)
          threadsPerThreadgroup:MTLSizeMake(LOCAL, 1, 1)];
      [encoder endEncoding];
      [command commit];
      [command waitUntilCompleted];
      if ([command status] != MTLCommandBufferStatusCompleted) {
         fprintf(stderr, "command failed: status=%ld error=%s\n",
                 (long)[command status],
                 [[[command error] localizedDescription] UTF8String]);
         return 1;
      }

      unsigned errors = 0;
      for (unsigned i = 0; i < COUNT; ++i) {
         const uint32_t before = 0x60000000u + 17u * i;
         const uint32_t operand = operand_value(i);
         Result expected = {
            before, before + operand, operand, i ^ 0xa917c0deu,
         };
         if (memcmp(&output[i], &expected, sizeof(expected)) ||
             target[i] != expected.new_value) {
            if (errors < 8)
               fprintf(stderr,
                       "mismatch %u out=%08x/%08x/%08x/%08x target=%08x "
                       "expected=%08x/%08x/%08x/%08x\n",
                       i, output[i].old_value, output[i].new_value,
                       output[i].operand, output[i].witness, target[i],
                       expected.old_value, expected.new_value,
                       expected.operand, expected.witness);
            ++errors;
         }
      }
      printf("RESULT exact=%u errors=%u\n", errors == 0, errors);
      return errors ? 1 : 0;
   }
}
