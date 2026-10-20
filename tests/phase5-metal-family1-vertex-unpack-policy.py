#!/usr/bin/env python3
"""Compile extracted production gating/helper with synthetic inputs; no GPU use."""

import argparse
from pathlib import Path
import subprocess
import tempfile


def function(source, marker):
    start = source.index(marker)
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[start:i + 1]
    raise SystemExit("unclosed production helper")


GATE_HARNESS = r'''
#include <cassert>
#include <string>
namespace gl { enum class ShaderType { Vertex, Fragment, Compute }; }
std::string envValue;
namespace angle { std::string GetEnvironmentVar(const char *) { return envValue; } }
enum { Mac1, Mac2 };
struct Device {
    bool mac1, mac2;
    int queries = 0;
    bool supportsFamily(int family) { ++queries; return family == Mac1 ? mac1 : mac2; }
};
HELPER
int main() {
    for (auto stage : {gl::ShaderType::Vertex, gl::ShaderType::Fragment, gl::ShaderType::Compute})
        for (const char *env : {"", "0", "1", "yes"})
            for (bool mac1 : {false, true}) for (bool mac2 : {false, true}) {
                envValue = env;
                Device device{mac1, mac2};
                bool enabled = UsePhase5VertexUnpackSnorm4x8(stage, &device);
                bool native = TARGET_OS_OSX && !TARGET_OS_MACCATALYST;
                bool eligible = native && stage == gl::ShaderType::Vertex && envValue == "1";
                assert(enabled == (eligible && mac1 && !mac2));
                assert(device.queries == (eligible ? 2 : 0));
            }
}
'''


DECODE_HARNESS = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstring>
namespace metal {
using uint = uint32_t;
template<class T> T as_type(uint u) { T t; static_assert(sizeof(t)==sizeof(u)); std::memcpy(&t,&u,sizeof(t)); return t; }
struct int4 { int v[4]; int4(int a,int b,int c,int d):v{a,b,c,d} {} };
struct float4 {
    float v[4];
    float4(float f):v{f,f,f,f} {}
    float4(int4 b):v{float(b.v[0]),float(b.v[1]),float(b.v[2]),float(b.v[3])} {}
};
float4 operator/(float4 a,float f) { for (auto &v:a.v) v/=f; return a; }
float4 max(float4 a,float4 b) { for(int c=0;c<4;++c) a.v[c]=std::max(a.v[c],b.v[c]); return a; }
}
HELPER
int main() {
    static_assert((-1 >> 1) == -1);
    for(unsigned lane=0;lane<4;++lane) for(unsigned byte=0;byte<256;++byte) {
        uint32_t word=(0x817f0180u & ~(255u<<(lane*8))) | (byte<<(lane*8));
        auto result=ANGLE_phase5::unpackSnorm4x8(word);
        for(unsigned c=0;c<4;++c) {
            int b=(word>>(c*8))&255; if(b>=128) b-=256;
            float expected=std::max(-1.0f,float(b)/127.0f);
            assert(std::isfinite(result.v[c]));
            assert(std::fabs(result.v[c]-expected)<0.000001f);
        }
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    root = args.source_root
    shader = (root / "src/libANGLE/renderer/metal/ShaderMtl.mm").read_text()
    emitter = (root / "src/compiler/translator/msl/EmitMetal.cpp").read_text()
    header = (root / "include/GLSLANG/ShaderLang.h").read_text()
    gate = function(shader, "static bool UsePhase5VertexUnpackSnorm4x8")
    for old, new in [("id<MTLDevice> metalDevice", "Device *metalDevice"),
                     ("[metalDevice supportsFamily:MTLGPUFamilyMac1]", "metalDevice->supportsFamily(Mac1)"),
                     ("[metalDevice supportsFamily:MTLGPUFamilyMac2]", "metalDevice->supportsFamily(Mac2)")]:
        if old not in gate:
            raise SystemExit("production gate shape changed")
        gate = gate.replace(old, new)
    start = emitter.index('out << R"phase5(') + len('out << R"phase5(')
    end = emitter.index(')phase5";', start)
    helper = emitter[start:end]
    required = ["mEmulateUnpackSnorm4x8(compileOptions.metal.emulateUnpackSnorm4x8)",
                "if (compileOptions.metal.emulateUnpackSnorm4x8)",
                'return "metal::unpack_snorm4x8_to_float";']
    if any(value not in emitter for value in required):
        raise SystemExit("production emitter option/default wiring missing")
    if emitter.count('? "ANGLE_phase5::unpackSnorm4x8"') != 2:
        raise SystemExit("both unary and aggregate call paths must use the option")
    if "bool emulateUnpackSnorm4x8 = false;" not in header:
        raise SystemExit("compatibility option must default to false")
    if "UsePhase5VertexUnpackSnorm4x8(mState.getShaderType(), displayMtl->getMetalDevice())" not in shader:
        raise SystemExit("production shader-stage/device gate is disconnected")
    with tempfile.TemporaryDirectory(prefix="synthetic-vertex-unpack-") as temp:
        temp = Path(temp)
        for mac, catalyst in [(1, 0), (1, 1), (0, 0)]:
            source = temp / "gate.cpp"
            source.write_text(GATE_HARNESS.replace("HELPER", gate))
            binary = temp / "gate"
            subprocess.run(["clang++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-UTARGET_OS_OSX", "-UTARGET_OS_MACCATALYST",
                            f"-DTARGET_OS_OSX={mac}", f"-DTARGET_OS_MACCATALYST={catalyst}",
                            str(source), "-o", str(binary)], check=True, timeout=60)
            subprocess.run([str(binary)], check=True, timeout=10)
        source = temp / "decode.cpp"
        source.write_text(DECODE_HARNESS.replace("HELPER", helper))
        binary = temp / "decode"
        subprocess.run(["clang++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(source), "-o", str(binary)], check=True, timeout=60)
        subprocess.run([str(binary)], check=True, timeout=10)
        metal = temp / "helper.metal"
        metal.write_text('#include <metal_stdlib>\n' + helper + r'''
struct SyntheticOut { metal::float4 position [[position]]; };
vertex SyntheticOut synthetic_vertex(uint i [[vertex_id]], constant uint &u [[buffer(0)]]) {
    return {metal::float4(float(i), ANGLE_phase5::unpackSnorm4x8(u).w, 0.5f, 1.0f)};
}
''')
        subprocess.run(["xcrun", "-sdk", "macosx", "metal", "-c", str(metal),
                        f"-fmodules-cache-path={temp / 'module-cache'}",
                        "-o", str(temp / "helper.air")], check=True, timeout=60)
    print("vertex-unpack policy: 144 gating cases, 1024 packed words, and offline MSL compilation passed; no GPU acceptance")


if __name__ == "__main__":
    main()
