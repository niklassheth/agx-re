// SPDX-License-Identifier: MIT
// Own-source T8132 Metal harness for an eight-visible-buffer compute carrier.

#import <Foundation/Foundation.h>
#import <Metal/Metal.h>

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    INPUT_COUNT = 7,
    VISIBLE_RESOURCE_COUNT = 8,
    GUARD_SIZE = 256,
};

typedef struct {
    uint32_t word[8];
} Result;

static const char *source =
    "#include <metal_stdlib>\n"
    "using namespace metal;\n"
    "struct Result { uint word[8]; };\n"
    "static inline uint pack3(uint3 v) {\n"
    "  return (v.x & 1023u) | ((v.y & 1023u) << 10) |"
    " ((v.z & 1023u) << 20);\n"
    "}\n"
    "kernel void carrier8(\n"
    "    device const uint *in0 [[buffer(0)]],\n"
    "    device const uint *in1 [[buffer(1)]],\n"
    "    device const uint *in2 [[buffer(2)]],\n"
    "    device const uint *in3 [[buffer(3)]],\n"
    "    device const uint *in4 [[buffer(4)]],\n"
    "    device const uint *in5 [[buffer(5)]],\n"
    "    device const uint *in6 [[buffer(6)]],\n"
    "    device Result *out [[buffer(7)]],\n"
    "    uint3 gid [[thread_position_in_grid]],\n"
    "    uint3 lid [[thread_position_in_threadgroup]],\n"
    "    uint3 group [[threadgroup_position_in_grid]],\n"
    "    uint3 local [[threads_per_threadgroup]],\n"
    "    uint3 grid [[threads_per_grid]],\n"
    "    uint3 groups [[threadgroups_per_grid]]) {\n"
    "  uint i = gid.x + grid.x * (gid.y + grid.y * gid.z);\n"
    "  uint h = 0x6d2b79f5u;\n"
    "  h = h * 33u + in0[i]; h = h * 33u + in1[i];\n"
    "  h = h * 33u + in2[i]; h = h * 33u + in3[i];\n"
    "  h = h * 33u + in4[i]; h = h * 33u + in5[i];\n"
    "  h = h * 33u + in6[i];\n"
    "  Result r = {{ h, i, pack3(gid), pack3(lid), pack3(group),"
    " pack3(local), pack3(grid), pack3(groups) }};\n"
    "  out[i] = r;\n"
    "}\n";

static uint32_t
input_value(unsigned slot, uint32_t index)
{
    return (index * (0x01010101u + slot * 0x00110011u)) ^
           (0xa5a50000u | (slot * 0x1111u + 0x31u));
}

static uint32_t
pack3(uint32_t x, uint32_t y, uint32_t z)
{
    return (x & 1023u) | ((y & 1023u) << 10) | ((z & 1023u) << 20);
}

static void
expected_result(Result *result, uint32_t gx, uint32_t gy, uint32_t gz,
                uint32_t lx, uint32_t ly, uint32_t lz,
                uint32_t x, uint32_t y, uint32_t z)
{
    uint32_t i = x + gx * (y + gy * z);
    uint32_t h = 0x6d2b79f5u;
    for (unsigned slot = 0; slot < INPUT_COUNT; ++slot)
        h = h * 33u + input_value(slot, i);

    const uint32_t groups_x = (gx + lx - 1) / lx;
    const uint32_t groups_y = (gy + ly - 1) / ly;
    const uint32_t groups_z = (gz + lz - 1) / lz;
    const uint32_t group_x = x / lx;
    const uint32_t group_y = y / ly;
    const uint32_t group_z = z / lz;
    const uint32_t actual_lx =
        (group_x + 1 == groups_x) ? gx - group_x * lx : lx;
    const uint32_t actual_ly =
        (group_y + 1 == groups_y) ? gy - group_y * ly : ly;
    const uint32_t actual_lz =
        (group_z + 1 == groups_z) ? gz - group_z * lz : lz;
    *result = (Result){{
        h,
        i,
        pack3(x, y, z),
        pack3(x % lx, y % ly, z % lz),
        pack3(group_x, group_y, group_z),
        pack3(actual_lx, actual_ly, actual_lz),
        pack3(gx, gy, gz),
        pack3(groups_x, groups_y, groups_z),
    }};
}

static unsigned long
parse_dimension(const char *name, const char *text)
{
    char *end = NULL;
    unsigned long value = strtoul(text, &end, 0);
    if (!text[0] || (end && *end) || value == 0 || value > 1023) {
        fprintf(stderr, "invalid %s: %s\n", name, text);
        exit(2);
    }
    return value;
}

int
main(int argc, char **argv)
{
    @autoreleasepool {
        uint32_t gx = 64, gy = 1, gz = 1;
        uint32_t lx = 16, ly = 1, lz = 1;
        unsigned offset_step = 0;
        for (int arg = 1; arg < argc; ++arg) {
            if (!strcmp(argv[arg], "--grid") && arg + 3 < argc) {
                gx = parse_dimension("grid x", argv[++arg]);
                gy = parse_dimension("grid y", argv[++arg]);
                gz = parse_dimension("grid z", argv[++arg]);
            } else if (!strcmp(argv[arg], "--local") && arg + 3 < argc) {
                lx = parse_dimension("local x", argv[++arg]);
                ly = parse_dimension("local y", argv[++arg]);
                lz = parse_dimension("local z", argv[++arg]);
            } else if (!strcmp(argv[arg], "--offset-step") && arg + 1 < argc) {
                offset_step = (unsigned)strtoul(argv[++arg], NULL, 0);
                if (offset_step & 3) {
                    fprintf(stderr, "offset step must be dword aligned\n");
                    return 2;
                }
            } else {
                fprintf(stderr,
                        "usage: %s [--grid X Y Z] [--local X Y Z]"
                        " [--offset-step BYTES]\n",
                        argv[0]);
                return 2;
            }
        }

        uint64_t local_threads = (uint64_t)lx * ly * lz;
        if (local_threads > 1024) {
            fprintf(stderr, "local size has too many threads\n");
            return 2;
        }
        size_t count = (size_t)gx * gy * gz;
        if (count > SIZE_MAX / sizeof(Result)) {
            fprintf(stderr, "grid is too large\n");
            return 2;
        }

        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        if (!device) {
            fprintf(stderr, "no Metal device\n");
            return 1;
        }
        NSError *error = nil;
        id<MTLLibrary> library =
            [device newLibraryWithSource:[NSString stringWithUTF8String:source]
                                 options:nil error:&error];
        if (!library) {
            fprintf(stderr, "compile failed: %s\n",
                    [[error localizedDescription] UTF8String]);
            return 1;
        }
        id<MTLFunction> function = [library newFunctionWithName:@"carrier8"];
        id<MTLComputePipelineState> pipeline =
            [device newComputePipelineStateWithFunction:function error:&error];
        if (!pipeline) {
            fprintf(stderr, "pipeline failed: %s\n",
                    [[error localizedDescription] UTF8String]);
            return 1;
        }

        id<MTLBuffer> buffers[VISIBLE_RESOURCE_COUNT] = {nil};
        NSUInteger offsets[VISIBLE_RESOURCE_COUNT] = {0};
        const uint8_t guard = 0xa5;
        for (unsigned slot = 0; slot < INPUT_COUNT; ++slot) {
            offsets[slot] = GUARD_SIZE + slot * offset_step;
            size_t payload = count * sizeof(uint32_t);
            buffers[slot] = [device
                newBufferWithLength:offsets[slot] + payload + GUARD_SIZE
                             options:MTLResourceStorageModeShared];
            memset([buffers[slot] contents], guard, [buffers[slot] length]);
            uint32_t *words = (uint32_t *)((uint8_t *)[buffers[slot] contents] +
                                           offsets[slot]);
            for (size_t i = 0; i < count; ++i)
                words[i] = input_value(slot, (uint32_t)i);
        }
        offsets[7] = GUARD_SIZE + 7 * offset_step;
        size_t output_size = count * sizeof(Result);
        buffers[7] = [device
            newBufferWithLength:offsets[7] + output_size + GUARD_SIZE
                         options:MTLResourceStorageModeShared];
        memset([buffers[7] contents], guard, [buffers[7] length]);

        printf("CASE grid=%ux%ux%u local=%ux%ux%u offset_step=%u\n",
               gx, gy, gz, lx, ly, lz, offset_step);
        for (unsigned slot = 0; slot < VISIBLE_RESOURCE_COUNT; ++slot) {
            printf("BUFFER slot=%u base=%#018" PRIx64 " offset=%#lx address=%#018" PRIx64
                   " size=%lu\n",
                   slot, (uint64_t)[buffers[slot] gpuAddress],
                   (unsigned long)offsets[slot],
                   (uint64_t)[buffers[slot] gpuAddress] + offsets[slot],
                   (unsigned long)[buffers[slot] length]);
        }
        fflush(stdout);

        id<MTLCommandQueue> queue = [device newCommandQueue];
        id<MTLCommandBuffer> command = [queue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
        [encoder setComputePipelineState:pipeline];
        for (unsigned slot = 0; slot < VISIBLE_RESOURCE_COUNT; ++slot)
            [encoder setBuffer:buffers[slot] offset:offsets[slot] atIndex:slot];
        [encoder dispatchThreads:MTLSizeMake(gx, gy, gz)
            threadsPerThreadgroup:MTLSizeMake(lx, ly, lz)];
        [encoder endEncoding];
        [command commit];
        [command waitUntilCompleted];
        if ([command status] != MTLCommandBufferStatusCompleted) {
            fprintf(stderr, "command failed: status=%ld error=%s\n",
                    (long)[command status],
                    [[[command error] localizedDescription] UTF8String]);
            return 1;
        }

        const uint8_t *output_base = [buffers[7] contents];
        const Result *actual =
            (const Result *)(output_base + offsets[7]);
        size_t mismatches = 0;
        for (uint32_t z = 0; z < gz; ++z) {
            for (uint32_t y = 0; y < gy; ++y) {
                for (uint32_t x = 0; x < gx; ++x) {
                    const size_t i = x + (size_t)gx * (y + (size_t)gy * z);
                    Result expected;
                    expected_result(&expected, gx, gy, gz, lx, ly, lz,
                                    x, y, z);
                    if (memcmp(&actual[i], &expected, sizeof(expected))) {
                        if (mismatches < 8) {
                            fprintf(stderr,
                                    "mismatch i=%zu\n  got     ", i);
                            for (unsigned word = 0; word < 8; ++word)
                                fprintf(stderr, " %08x", actual[i].word[word]);
                            fprintf(stderr, "\n  expected");
                            for (unsigned word = 0; word < 8; ++word)
                                fprintf(stderr, " %08x", expected.word[word]);
                            fprintf(stderr, "\n");
                        }
                        ++mismatches;
                    }
                }
            }
        }
        size_t guard_errors = 0;
        for (unsigned slot = 0; slot < VISIBLE_RESOURCE_COUNT; ++slot) {
            const uint8_t *bytes = [buffers[slot] contents];
            for (NSUInteger i = 0; i < offsets[slot]; ++i)
                guard_errors += bytes[i] != guard;
            size_t payload = slot == 7 ? output_size : count * sizeof(uint32_t);
            for (NSUInteger i = offsets[slot] + payload;
                 i < [buffers[slot] length]; ++i)
                guard_errors += bytes[i] != guard;
        }
        printf("RESULT exact=%u mismatches=%zu guard_errors=%zu invocations=%zu\n",
               mismatches == 0 && guard_errors == 0,
               mismatches, guard_errors, count);
        return mismatches || guard_errors ? 1 : 0;
    }
}
