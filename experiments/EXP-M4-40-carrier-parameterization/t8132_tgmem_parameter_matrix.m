// Own-source Metal probe for T8132 threadgroup-memory package parameters.
// The same dynamic pipeline is dispatched with several allocation sizes.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum {
  ELEMENTS = 64,
  LOCAL = 32,
  BUFFER_SIZE = 0x1000,
};

static uint32_t input_word(unsigned i) {
  uint32_t x = 0x243f6a88u ^ i * 0x9e3779b9u;
  x ^= x >> 16;
  x *= 0x7feb352du;
  x ^= x >> 15;
  return x ^ (i << 17);
}

static uint32_t expected_word(const uint32_t *input, unsigned gid) {
  unsigned group = gid / LOCAL;
  unsigned lid = gid % LOCAL;
  unsigned peer = (lid * 13u + 7u) & 31u;
  unsigned peer_gid = group * LOCAL + peer;
  uint32_t scratch = input[peer_gid] ^ (0x9e3779b9u + group * 0x01010101u);
  return (scratch + gid * 0x00010203u) ^ 0xd1b54a35u;
}

static int run_case(id<MTLDevice> device, id<MTLCommandQueue> queue,
                    id<MTLComputePipelineState> pipeline, const char *name,
                    NSUInteger dynamic_bytes, id<MTLBuffer> input,
                    const uint8_t expected[BUFFER_SIZE]) {
  id<MTLBuffer> output =
      [device newBufferWithLength:BUFFER_SIZE
                          options:MTLResourceStorageModeShared];
  if (!output)
    return 1;
  memset([output contents], 0xcc, BUFFER_SIZE);

  id<MTLCommandBuffer> command = [queue commandBuffer];
  id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
  [encoder setComputePipelineState:pipeline];
  [encoder setBuffer:input offset:0 atIndex:0];
  [encoder setBuffer:output offset:0 atIndex:1];
  if (dynamic_bytes)
    [encoder setThreadgroupMemoryLength:dynamic_bytes atIndex:0];
  [encoder dispatchThreads:MTLSizeMake(ELEMENTS, 1, 1)
      threadsPerThreadgroup:MTLSizeMake(LOCAL, 1, 1)];
  [encoder endEncoding];
  [command commit];
  [command waitUntilCompleted];

  if (command.status != MTLCommandBufferStatusCompleted) {
    fprintf(stderr, "COMMAND_FAIL case=%s status=%ld error=%s\n", name,
            (long)command.status,
            command.error.localizedDescription.UTF8String);
    return 1;
  }
  if (memcmp([output contents], expected, BUFFER_SIZE) != 0) {
    const uint32_t *actual = [output contents];
    const uint32_t *oracle = (const uint32_t *)expected;
    for (unsigned i = 0; i < BUFFER_SIZE / sizeof(uint32_t); ++i) {
      if (actual[i] != oracle[i]) {
        fprintf(stderr, "MISMATCH case=%s word=%u got=%#x expected=%#x\n", name,
                i, actual[i], oracle[i]);
        break;
      }
    }
    return 1;
  }

  printf("TGMEM_CASE_OK name=%s dynamic=%lu static=%lu exact=1 guard=%u\n",
         name, (unsigned long)dynamic_bytes,
         (unsigned long)pipeline.staticThreadgroupMemoryLength,
         BUFFER_SIZE - ELEMENTS * (unsigned)sizeof(uint32_t));
  fflush(stdout);
  return 0;
}

int main(void) {
  @autoreleasepool {
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
                        "kernel void dynamic_shared("
                        "device const uint *a [[buffer(0)]], "
                        "device uint *out [[buffer(1)]], "
                        "threadgroup uint *scratch [[threadgroup(0)]], "
                        "uint gid [[thread_position_in_grid]], "
                        "uint lid [[thread_position_in_threadgroup]], "
                        "uint group [[threadgroup_position_in_grid]]) { "
                        "scratch[lid] = a[gid] ^ "
                        "(0x9e3779b9u + group * 0x01010101u); "
                        "threadgroup_barrier(mem_flags::mem_threadgroup); "
                        "uint peer = (lid * 13u + 7u) & 31u; "
                        "out[gid] = (scratch[peer] + gid * 0x00010203u) ^ "
                        "0xd1b54a35u; }\n"
                        "kernel void static_shared("
                        "device const uint *a [[buffer(0)]], "
                        "device uint *out [[buffer(1)]], "
                        "uint gid [[thread_position_in_grid]], "
                        "uint lid [[thread_position_in_threadgroup]], "
                        "uint group [[threadgroup_position_in_grid]]) { "
                        "threadgroup uint scratch[32]; "
                        "scratch[lid] = a[gid] ^ "
                        "(0x9e3779b9u + group * 0x01010101u); "
                        "threadgroup_barrier(mem_flags::mem_threadgroup); "
                        "uint peer = (lid * 13u + 7u) & 31u; "
                        "out[gid] = (scratch[peer] + gid * 0x00010203u) ^ "
                        "0xd1b54a35u; }\n";

    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    if (!device) {
      fprintf(stderr, "NO_METAL_DEVICE\n");
      return 1;
    }
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source
                                                  options:nil
                                                    error:&error];
    if (!library) {
      fprintf(stderr, "COMPILE_FAIL %s\n",
              error.localizedDescription.UTF8String);
      return 1;
    }
    id<MTLFunction> dynamic_function =
        [library newFunctionWithName:@"dynamic_shared"];
    id<MTLFunction> static_function =
        [library newFunctionWithName:@"static_shared"];
    id<MTLComputePipelineState> dynamic_pipeline =
        [device newComputePipelineStateWithFunction:dynamic_function
                                              error:&error];
    if (!dynamic_pipeline) {
      fprintf(stderr, "DYNAMIC_PIPELINE_FAIL %s\n",
              error.localizedDescription.UTF8String);
      return 1;
    }
    id<MTLComputePipelineState> static_pipeline =
        [device newComputePipelineStateWithFunction:static_function
                                              error:&error];
    if (!static_pipeline) {
      fprintf(stderr, "STATIC_PIPELINE_FAIL %s\n",
              error.localizedDescription.UTF8String);
      return 1;
    }

    id<MTLBuffer> input =
        [device newBufferWithLength:BUFFER_SIZE
                            options:MTLResourceStorageModeShared];
    if (!input)
      return 1;
    uint32_t *input_words = [input contents];
    for (unsigned i = 0; i < BUFFER_SIZE / sizeof(uint32_t); ++i)
      input_words[i] = input_word(i);
    uint8_t input_before[BUFFER_SIZE];
    memcpy(input_before, input_words, BUFFER_SIZE);

    _Alignas(uint32_t) uint8_t expected[BUFFER_SIZE];
    memset(expected, 0xcc, sizeof(expected));
    uint32_t *expected_words = (uint32_t *)expected;
    for (unsigned i = 0; i < ELEMENTS; ++i)
      expected_words[i] = expected_word(input_words, i);

    printf("TGMEM_MATRIX_BEGIN device=%s dynamic_static=%lu static_static=%lu "
           "dynamic_width=%lu static_width=%lu\n",
           device.name.UTF8String,
           (unsigned long)dynamic_pipeline.staticThreadgroupMemoryLength,
           (unsigned long)static_pipeline.staticThreadgroupMemoryLength,
           (unsigned long)dynamic_pipeline.threadExecutionWidth,
           (unsigned long)static_pipeline.threadExecutionWidth);
    id<MTLCommandQueue> queue = [device newCommandQueue];
    const NSUInteger sizes[] = {128, 256, 512, 1024};
    for (unsigned i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
      char name[32];
      snprintf(name, sizeof(name), "dynamic_%lu", (unsigned long)sizes[i]);
      if (run_case(device, queue, dynamic_pipeline, name, sizes[i], input,
                   expected))
        return 1;
    }
    if (run_case(device, queue, static_pipeline, "static_128", 0, input,
                 expected))
      return 1;
    if (memcmp(input_words, input_before, BUFFER_SIZE) != 0) {
      fprintf(stderr, "INPUT_MUTATION\n");
      return 1;
    }
    printf("TGMEM_MATRIX_OK cases=5 input_immutable=1\n");
    return 0;
  }
}
