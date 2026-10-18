// Standalone diagnostic for the packed flip uniform used by ANGLE's Metal backend.
// All inputs are synthetic. Results are diagnostics, never device acceptance.
// Source boundary: ANGLE 8efd15f71c27cd0bc2a9cf0074d77e899ca9c448,
// ContextMtl, DriverUniform::getFlipXY, TranslatorMSL and EmitMetal.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <simd/simd.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>

struct DriverUniforms
{
    float depthRange[2];
    uint32_t renderArea, flipXY, misc, unused, acbBufferOffsets[2];
    int32_t xfbBufferOffsets[4], xfbVerticesPerInstance;
    uint32_t coverageMask, unused2[2];
};
static_assert(sizeof(DriverUniforms) == 64);
static_assert(offsetof(DriverUniforms, flipXY) == 12);

static NSString *ShaderSource()
{
    return [NSString stringWithUTF8String:R"metal(
#include <metal_stdlib>
using namespace metal;
struct DriverUniforms {
    float2 depthRange;
    uint renderArea, flipXY, misc, unused;
    uint2 acbBufferOffsets;
    int4 xfbBufferOffsets;
    int xfbVerticesPerInstance;
    uint coverageMask;
    uint2 unused2;
};
float4 scalarDecode(uint u) {
    int4 b = int4(as_type<int>(u << 24) >> 24, as_type<int>(u << 16) >> 24,
                  as_type<int>(u << 8) >> 24, as_type<int>(u) >> 24);
    return max(float4(b) / 127.0f, float4(-1.0f));
}
kernel void decodeProbe(device const uint *inputs [[buffer(0)]],
                        device float4 *results [[buffer(1)]],
                        uint i [[thread_position_in_grid]]) {
    results[2*i] = unpack_snorm4x8_to_float(inputs[i]);
    results[2*i+1] = scalarDecode(inputs[i]);
}
struct VertexOut { float4 position [[position]]; };
vertex VertexOut vertexBase(uint i [[vertex_id]], constant float2 *p [[buffer(0)]]) {
    return {float4(p[i], 0.5f, 1.0f)};
}
vertex VertexOut vertexBuiltin(uint i [[vertex_id]], constant float2 *p [[buffer(0)]],
                               constant DriverUniforms &u [[buffer(17)]]) {
    VertexOut v = {float4(p[i], 0.5f, 1.0f)};
    v.position.y *= unpack_snorm4x8_to_float(u.flipXY).w;
    return v;
}
vertex VertexOut vertexScalar(uint i [[vertex_id]], constant float2 *p [[buffer(0)]],
                              constant DriverUniforms &u [[buffer(17)]]) {
    VertexOut v = {float4(p[i], 0.5f, 1.0f)};
    v.position.y *= scalarDecode(u.flipXY).w;
    return v;
}
fragment float4 green() { return float4(0.0f, 1.0f, 0.0f, 1.0f); }
)metal"];
}

static bool Completed(id<MTLCommandBuffer> command)
{
    if (!command) return false;
    dispatch_semaphore_t done = dispatch_semaphore_create(0);
    [command addCompletedHandler:^(id<MTLCommandBuffer>) { dispatch_semaphore_signal(done); }];
    [command commit];
    if (dispatch_semaphore_wait(done, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC)))
        return false;
    return command.status == MTLCommandBufferStatusCompleted;
}

static NSArray *Components(const simd_float4 &value)
{
    NSMutableArray *out = [NSMutableArray array];
    for (unsigned c = 0; c < 4; ++c)
        [out addObject:std::isfinite(value[c]) ? (id)@(value[c]) : (id)[NSNull null]];
    return out;
}

static bool Near(const simd_float4 &a, const simd_float4 &b)
{
    for (unsigned c = 0; c < 4; ++c)
        if (!std::isfinite(a[c]) || std::fabs(a[c] - b[c]) > 1e-6f) return false;
    return true;
}

static bool Decode(id<MTLDevice> device, id<MTLCommandQueue> queue, id<MTLLibrary> library,
                   NSMutableDictionary *mode)
{
    const uint32_t inputs[] = {0, 0x7f7f7f7f, 0x817f7f7f, 0x7f817f81,
                               0x80808080, 0x807fff01, 0xff00817f};
    constexpr unsigned count = sizeof(inputs) / sizeof(inputs[0]);
    NSError *error = nil;
    id<MTLFunction> function = [library newFunctionWithName:@"decodeProbe"];
    id<MTLComputePipelineState> pipeline = [device newComputePipelineStateWithFunction:function error:&error];
    id<MTLBuffer> input = [device newBufferWithBytes:inputs length:sizeof(inputs) options:MTLResourceStorageModeShared];
    id<MTLBuffer> output = [device newBufferWithLength:count * 2 * sizeof(simd_float4) options:MTLResourceStorageModeShared];
    if (!pipeline || !input || !output) return false;
    std::memset(output.contents, 0, output.length);
    id<MTLCommandBuffer> command = [queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
    if (!encoder) return false;
    [encoder setComputePipelineState:pipeline];
    [encoder setBuffer:input offset:0 atIndex:0];
    [encoder setBuffer:output offset:0 atIndex:1];
    [encoder dispatchThreadgroups:MTLSizeMake(count, 1, 1) threadsPerThreadgroup:MTLSizeMake(1, 1, 1)];
    [encoder endEncoding];
    if (!Completed(command)) return false;
    const simd_float4 *values = static_cast<const simd_float4 *>(output.contents);
    NSMutableArray *cases = [NSMutableArray array];
    for (unsigned i = 0; i < count; ++i)
    {
        simd_float4 reference;
        for (unsigned c = 0; c < 4; ++c)
        {
            int byte = (inputs[i] >> (8 * c)) & 255;
            if (byte >= 128) byte -= 256;
            reference[c] = std::max(-1.0f, static_cast<float>(byte) / 127.0f);
        }
        [cases addObject:@{@"synthetic_case":@(i), @"builtin":Components(values[2*i]),
                          @"scalar":Components(values[2*i+1]), @"reference":Components(reference),
                          @"builtin_matches":@(Near(values[2*i], reference)),
                          @"scalar_matches":@(Near(values[2*i+1], reference))}];
    }
    mode[@"decode_cases"] = cases;
    return true;
}

static bool Render(id<MTLDevice> device, id<MTLCommandQueue> queue, id<MTLLibrary> library,
                   NSMutableDictionary *mode)
{
    NSMutableArray *cases = [NSMutableArray array];
    const simd_float2 positions[] = {{-0.75f,-0.75f}, {0.75f,-0.75f}, {0,0.75f}};
    const uint32_t flips[] = {0x7f7f7f7f, 0x817f7f7f};
    for (NSString *variant in @[@"vertexBase", @"vertexBuiltin", @"vertexScalar"])
    {
        MTLRenderPipelineDescriptor *pipelineDesc = [MTLRenderPipelineDescriptor new];
        pipelineDesc.vertexFunction = [library newFunctionWithName:variant];
        pipelineDesc.fragmentFunction = [library newFunctionWithName:@"green"];
        pipelineDesc.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
        NSError *error = nil;
        id<MTLRenderPipelineState> pipeline = [device newRenderPipelineStateWithDescriptor:pipelineDesc error:&error];
        if (!pipeline) return false;
        for (unsigned sign = 0; sign < 2; ++sign)
        {
            MTLTextureDescriptor *textureDesc = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:32 height:32 mipmapped:NO];
            textureDesc.storageMode = MTLStorageModeManaged;
            textureDesc.usage = MTLTextureUsageRenderTarget;
            id<MTLTexture> texture = [device newTextureWithDescriptor:textureDesc];
            if (!texture) return false;
            DriverUniforms uniforms{};
            uniforms.depthRange[1] = 1;
            uniforms.renderArea = (32u << 16) | 32u;
            uniforms.flipXY = flips[sign];
            uniforms.coverageMask = 0xffffffff;
            MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
            pass.colorAttachments[0].texture = texture;
            pass.colorAttachments[0].loadAction = MTLLoadActionClear;
            pass.colorAttachments[0].storeAction = MTLStoreActionStore;
            pass.colorAttachments[0].clearColor = MTLClearColorMake(0,0,0,1);
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
            if (!encoder) return false;
            [encoder setRenderPipelineState:pipeline];
            [encoder setCullMode:MTLCullModeNone];
            [encoder setViewport:(MTLViewport){0,0,32,32,0,1}];
            [encoder setVertexBytes:positions length:sizeof(positions) atIndex:0];
            [encoder setVertexBytes:&uniforms length:sizeof(uniforms) atIndex:17];
            [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
            [encoder endEncoding];
            id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
            if (!blit) return false;
            [blit synchronizeResource:texture];
            [blit endEncoding];
            if (!Completed(command)) return false;
            uint8_t pixels[32 * 32 * 4] = {};
            [texture getBytes:pixels bytesPerRow:32*4 fromRegion:MTLRegionMake2D(0,0,32,32) mipmapLevel:0];
            unsigned greenCount = 0;
            for (unsigned i = 0; i < 32*32; ++i)
                greenCount += pixels[4*i] == 0 && pixels[4*i+1] == 255 && pixels[4*i+2] == 0 && pixels[4*i+3] == 255;
            const uint8_t *center = pixels + (16*32+16)*4;
            [cases addObject:@{@"variant":variant, @"synthetic_flip_sign":@(sign),
                              @"center_pixel":@[@(center[0]),@(center[1]),@(center[2]),@(center[3])],
                              @"green_pixel_count":@(greenCount), @"center_green":@(center[0]==0 && center[1]==255 && center[2]==0 && center[3]==255)}];
        }
    }
    mode[@"render_cases"] = cases;
    return true;
}

int main(int argc, const char *argv[])
{
    @autoreleasepool
    {
        // Compilation is preparation. GPU execution requires a separate explicit --run.
        if (argc != 4 || std::strcmp(argv[1], "--run") != 0 ||
            std::strcmp(argv[2], "--out") != 0) return 64;
        int fd = open(argv[3], O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
        if (fd < 0) return 73;
        NSMutableDictionary *report = [@{@"diagnostic_only":@YES, @"device_acceptance":@NO,
                                         @"synthetic_inputs_only":@YES} mutableCopy];
        NSMutableArray *modes = [NSMutableArray array];
        id<MTLDevice> device = MTLCreateSystemDefaultDevice();
        id<MTLCommandQueue> queue = [device newCommandQueue];
        bool complete = device && queue;
        for (NSNumber *fast in @[@NO,@YES])
        {
            if (!complete) break;
            MTLCompileOptions *options = [MTLCompileOptions new];
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wdeprecated-declarations"
            options.fastMathEnabled = fast.boolValue;
#pragma clang diagnostic pop
            NSError *error = nil;
            id<MTLLibrary> library = [device newLibraryWithSource:ShaderSource() options:options error:&error];
            NSMutableDictionary *mode = [@{@"fast_math_enabled":fast,
                                           @"default_language_version":@(options.languageVersion),
                                           @"library_compiled":@(library != nil)} mutableCopy];
            [modes addObject:mode];
            complete = false;
            if (!library) mode[@"failed_stage"] = @"library_compile";
            else if (!Decode(device,queue,library,mode)) mode[@"failed_stage"] = @"decode";
            else if (!Render(device,queue,library,mode)) mode[@"failed_stage"] = @"render";
            else complete = true;
        }
        report[@"modes"] = modes;
        report[@"completed"] = @(complete);
        NSData *json = [NSJSONSerialization dataWithJSONObject:report options:NSJSONWritingPrettyPrinted error:nullptr];
        bool written = json != nil;
        const uint8_t *bytes = static_cast<const uint8_t *>(json.bytes);
        size_t remaining = json.length;
        while (written && remaining)
        {
            ssize_t n = write(fd,bytes,remaining);
            if (n <= 0) { written = false; break; }
            bytes += n; remaining -= static_cast<size_t>(n);
        }
        close(fd);
        std::puts(complete && written ? "METAL_FLIP_DIAGNOSTIC_REVIEW_PENDING" : "METAL_FLIP_DIAGNOSTIC_INCOMPLETE");
        return complete && written ? 0 : 2;
    }
}
