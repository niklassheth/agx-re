// SPDX-License-Identifier: MIT
// Our source and public Metal API only. No binary introspection.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdio.h>
int main(int argc, const char **argv) {
 @autoreleasepool {
  NSError *e = nil;
  id<MTLDevice> dev = MTLCreateSystemDefaultDevice();
  NSString *s = [NSString stringWithContentsOfFile:[NSString stringWithUTF8String:argc > 1 ? argv[1] : "probe-varyings.metal"] encoding:NSUTF8StringEncoding error:&e];
  id<MTLLibrary> lib = [dev newLibraryWithSource:s options:nil error:&e];
  if (!lib) { NSLog(@"%@", e); return 1; }
  MTLRenderPipelineDescriptor *p = [MTLRenderPipelineDescriptor new];
  p.vertexFunction = [lib newFunctionWithName:@"v_main"];
  p.fragmentFunction = [lib newFunctionWithName:@"f_main"];
  p.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
  BOOL depth = NO;
  if (depth) p.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float;
  MTLBinaryArchiveDescriptor *ad = [MTLBinaryArchiveDescriptor new];
  id<MTLBinaryArchive> ar = [dev newBinaryArchiveWithDescriptor:ad error:&e];
  [ar addRenderPipelineFunctionsWithDescriptor:p error:&e];
  [ar serializeToURL:[NSURL fileURLWithPath:depth ? @"probe-mesh-depth.bin" : @"probe-mesh.bin"] error:&e];
  id<MTLRenderPipelineState> ps = [dev newRenderPipelineStateWithDescriptor:p error:&e];
  if (!ps) { NSLog(@"%@", e); return 1; }
  MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:512 height:512 mipmapped:NO];
  td.usage = MTLTextureUsageRenderTarget; td.storageMode = MTLStorageModeShared;
  id<MTLTexture> color = [dev newTextureWithDescriptor:td];
  MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor new];
  rp.colorAttachments[0].texture = color;
  rp.colorAttachments[0].loadAction = MTLLoadActionClear;
  rp.colorAttachments[0].storeAction = MTLStoreActionStore;
  rp.colorAttachments[0].clearColor = MTLClearColorMake(4./255,5./255,15./255,1);
  id<MTLDepthStencilState> ds = nil;
  if (depth) {
   td.pixelFormat = MTLPixelFormatDepth32Float;
   rp.depthAttachment.texture = [dev newTextureWithDescriptor:td];
   rp.depthAttachment.loadAction = MTLLoadActionClear;
   rp.depthAttachment.storeAction = MTLStoreActionStore;
   rp.depthAttachment.clearDepth = 1;
   MTLDepthStencilDescriptor *dd = [MTLDepthStencilDescriptor new];
   dd.depthCompareFunction = MTLCompareFunctionLess;
   dd.depthWriteEnabled = YES;
   ds = [dev newDepthStencilStateWithDescriptor:dd];
  }
  const float verts[12] = {-.75,-.75,.25,1, .75,-.75,.25,1, 0,.75,.25,1};
  id<MTLCommandQueue> q = [dev newCommandQueue];
  id<MTLCommandBuffer> cb = [q commandBuffer];
  id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
  [re setRenderPipelineState:ps]; if (depth) [re setDepthStencilState:ds];
  for (unsigned stage=0; stage<2; ++stage) for (unsigned slot=0; slot<4; ++slot) {
   float data[12];
   for (unsigned i=0;i<12;++i) data[i] = .03125f * (1 + stage*32 + slot*4 + i%4);
   if (stage==0 && slot==0) memcpy(data,verts,sizeof(data));
   if (stage==0) [re setVertexBytes:data length:sizeof(data) atIndex:slot];
   else [re setFragmentBytes:data length:sizeof(data) atIndex:slot];
  }
  uint16_t indices[] = {0,1,2};
  id<MTLBuffer> ib = [dev newBufferWithBytes:indices length:sizeof(indices) options:MTLResourceStorageModeShared];
  [re drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt16 indexBuffer:ib indexBufferOffset:0];
  [re endEncoding]; [cb commit]; [cb waitUntilCompleted];
  printf("status=%lu\n", (unsigned long)cb.status);
  if (cb.error) NSLog(@"%@", cb.error);
  unsigned char *pixels = malloc(512*512*4);
  [color getBytes:pixels bytesPerRow:512*4 fromRegion:MTLRegionMake2D(0,0,512,512) mipmapLevel:0];
  FILE *f = fopen(depth ? "probe-mesh-depth.bgra" : "probe-mesh.bgra", "wb");
  fwrite(pixels,1,512*512*4,f); fclose(f); free(pixels);
  return cb.status == MTLCommandBufferStatusCompleted ? 0 : 1;
 }
}
