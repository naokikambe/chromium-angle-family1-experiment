#!/usr/bin/env python3
"""Compile extracted ANGLE math-option logic with synthetic Metal receivers.

The fixture exercises production helper and modern math-option branch logic;
it does not compile ANGLE or claim Metal runtime acceptance.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

HELPER = "static bool UseLegacyMathOptionsForPhase5Family1"
AVAILABLE = "if (@available(macOS 15.0, iOS 18.0, *))"
SDK_GUARD = (
    "#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000 || "
    "__IPHONE_OS_VERSION_MAX_ALLOWED >= 180000 || "
    "__TV_OS_VERSION_MAX_ALLOWED >= 180000 || TARGET_OS_VISION"
)


def braced_body(source: str, opening: int) -> str:
    brace = source.find("{", opening)
    depth = 0
    for end in range(brace, len(source)):
        if source[end] == "{":
            depth += 1
        elif source[end] == "}":
            depth -= 1
            if depth == 0:
                return source[brace + 1 : end]
    raise SystemExit("unclosed production source block")


def synthetic_helper(source: str) -> str:
    start = source.find(HELPER)
    if start < 0:
        raise SystemExit("patched mtl_utils.mm lacks the Family 1 selector helper")
    brace = source.find("{", start)
    body = braced_body(source, start)
    end = source.find(body, brace) + len(body) + 1
    function = source[start:end]
    replacements = (
        ("id<MTLDevice> metalDevice", "Device *metalDevice"),
        ("MTLCompileOptions *options", "CompileOptions *options"),
        (
            'angle::GetEnvironmentVar("ANGLE_PHASE5_ENABLE_METAL_FAMILY1") != "1"',
            'envValue != "1"',
        ),
        ("[metalDevice supportsFamily:MTLGPUFamilyMac1]", "metalDevice->supportsFamily(Mac1)"),
        ("[metalDevice supportsFamily:MTLGPUFamilyMac2]", "metalDevice->supportsFamily(Mac2)"),
        (
            "[options respondsToSelector:@selector(setMathMode:)]",
            "options->respondsToSelector(MathModeSetter)",
        ),
        (
            "[options respondsToSelector:@selector(setMathFloatingPointFunctions:)]",
            "options->respondsToSelector(MathFunctionsSetter)",
        ),
    )
    for old, new in replacements:
        if old not in function:
            raise SystemExit(f"could not translate production helper expression: {old}")
        function = function.replace(old, new)
    return function


def synthetic_modern_branch(source: str) -> str:
    start = source.find(AVAILABLE)
    if start < 0:
        raise SystemExit("CreateShaderLibrary lacks the modern availability branch")
    body = braced_body(source, start)
    body = body.replace(
        "UseLegacyMathOptionsForPhase5Family1(metalDevice, options.get())",
        "UseLegacyMathOptionsForPhase5Family1(metalDevice, &options)",
    )
    body = re.sub(r"options\.get\(\)\.fastMathEnabled\s*=\s*!disableFastMath;",
                  "options.setLegacyFastMath(!disableFastMath);", body)
    body = re.sub(r"options\.get\(\)\.mathMode\s*=\s*(\w+);",
                  r"options.setMathMode(\1);", body)
    body = re.sub(
        r"options\.get\(\)\.mathFloatingPointFunctions\s*=\s*(\w+);",
        r"options.setMathFunctions(\1);", body)
    if "options.get()" in body:
        raise SystemExit("untranslated options.get() remains in the production branch")
    return body


HARNESS = r"""
#include <cassert>
#include <cstdio>
#include <string>
#ifndef TARGET_OS_VISION
#define TARGET_OS_VISION 0
#endif
enum { Mac1 = 1, Mac2 = 2, MathModeSetter = 3, MathFunctionsSetter = 4 };
enum { MTLMathModeSafe = 11, MTLMathModeFast = 12,
       MTLMathFloatingPointFunctionsPrecise = 21,
       MTLMathFloatingPointFunctionsFast = 22 };
std::string envValue;
struct Device {
    bool mac1;
    bool mac2;
    bool supportsFamily(int family) const { return family == Mac1 ? mac1 : mac2; }
};
struct CompileOptions {
    bool mathModeAvailable;
    bool mathFunctionsAvailable;
    bool legacyFastMath = false;
    int mathMode = 0;
    int mathFunctions = 0;
    int mathModeWrites = 0;
    int mathFunctionsWrites = 0;
    bool respondsToSelector(int selector) const {
        return selector == MathModeSetter ? mathModeAvailable : mathFunctionsAvailable;
    }
    void setLegacyFastMath(bool value) { legacyFastMath = value; }
    void setMathMode(int value) {
        assert(mathModeAvailable);
        ++mathModeWrites;
        mathMode = value;
    }
    void setMathFunctions(int value) {
        assert(mathFunctionsAvailable);
        ++mathFunctionsWrites;
        mathFunctions = value;
    }
};
#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000 || __IPHONE_OS_VERSION_MAX_ALLOWED >= 180000 || \
    __TV_OS_VERSION_MAX_ALLOWED >= 180000 || TARGET_OS_VISION
@@HELPER@@
void configure(Device *metalDevice, CompileOptions &options, bool disableFastMath) {
@@BRANCH@@
}
#endif
int main() {
#if __MAC_OS_X_VERSION_MAX_ALLOWED >= 150000 || __IPHONE_OS_VERSION_MAX_ALLOWED >= 180000 || \
    __TV_OS_VERSION_MAX_ALLOWED >= 180000 || TARGET_OS_VISION
    auto check = [](const char *env, bool mac1, bool mac2, bool mode, bool funcs,
                    bool expected) {
        envValue = env;
        Device device{mac1, mac2};
        CompileOptions options{mode, funcs};
        assert(UseLegacyMathOptionsForPhase5Family1(&device, &options) == expected);
    };
#if TARGET_OS_OSX && !TARGET_OS_MACCATALYST
    check("1", true, false, false, false, true);  // both modern setters absent
    check("1", true, false, true, false, true);   // mathMode setter absent
    check("1", true, false, false, true, true);   // floating-functions setter absent
    check("1", true, false, true, true, false);   // modern pair available
    check("", true, false, false, false, false);
    check("true", true, false, false, false, false);
    check("1 ", true, false, false, false, false);
    check("1", false, false, false, false, false);
    check("1", true, true, false, false, false);  // Family 2 is untouched
    check("1", false, true, false, false, false);

    envValue = "1";
    Device family1{true, false};
    CompileOptions missingBoth{false, false};
    configure(&family1, missingBoth, false);
    assert(missingBoth.legacyFastMath);
    assert(missingBoth.mathModeWrites == 0 && missingBoth.mathFunctionsWrites == 0);
    CompileOptions missingMode{false, true};
    configure(&family1, missingMode, true);
    assert(!missingMode.legacyFastMath);
    assert(missingMode.mathModeWrites == 0 && missingMode.mathFunctionsWrites == 0);
    CompileOptions missingFunctions{true, false};
    configure(&family1, missingFunctions, false);
    assert(missingFunctions.legacyFastMath);
    assert(missingFunctions.mathModeWrites == 0 && missingFunctions.mathFunctionsWrites == 0);

    CompileOptions safe{true, true};
    configure(&family1, safe, true);
    assert(safe.mathMode == MTLMathModeSafe);
    assert(safe.mathFunctions == MTLMathFloatingPointFunctionsPrecise);
    assert(safe.mathModeWrites == 1 && safe.mathFunctionsWrites == 1);
    assert(!safe.legacyFastMath);
    CompileOptions fast{true, true};
    configure(&family1, fast, false);
    assert(fast.mathMode == MTLMathModeFast);
    assert(fast.mathFunctions == MTLMathFloatingPointFunctionsFast);
    assert(fast.mathModeWrites == 1 && fast.mathFunctionsWrites == 1);

    envValue = "";
    CompileOptions defaultPath{true, true};
    configure(&family1, defaultPath, true);
    assert(defaultPath.mathMode == MTLMathModeSafe);
    assert(defaultPath.mathFunctions == MTLMathFloatingPointFunctionsPrecise);
#elif TARGET_OS_MACCATALYST
    check("1", true, false, false, false, false);  // Catalyst remains unchanged
#else
    check("1", true, false, false, false, false);  // Other platforms unchanged
#endif
#endif
    return 0;
}
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mtl-utils", required=True, type=Path)
    args = parser.parse_args()
    source = args.mtl_utils.read_text()
    helper = synthetic_helper(source)
    branch = synthetic_modern_branch(source)
    helper_index = source.index(HELPER)
    guard_region = source[max(0, helper_index - 220) : helper_index]
    guard_region = re.sub(r"\\\s*", " ", guard_region)
    guard_region = re.sub(r"\s+", " ", guard_region)
    guard = re.sub(r"\\\s*", " ", SDK_GUARD)
    guard = re.sub(r"\s+", " ", guard)
    if guard not in guard_region:
        raise SystemExit("selector helper is not limited to the modern SDK compile branch")

    variants = (
        ("macos-sdk14", 1, 0, 140000, 140000, 130000),
        ("macos-sdk15", 1, 0, 150000, 150000, 130000),
        ("catalyst-sdk17", 0, 1, 140000, 170000, 150000),
        ("catalyst-sdk18", 0, 1, 140000, 180000, 150000),
        ("ios-device-sdk18", 0, 0, 140000, 180000, 170000),
    )
    with tempfile.TemporaryDirectory(prefix="phase5-math-options-policy-") as temp:
        for name, is_osx, catalyst, mac_sdk, ios_sdk, min_version in variants:
            source_text = (HARNESS.replace("@@HELPER@@", helper)
                           .replace("@@BRANCH@@", branch))
            output = Path(temp) / name
            command = [
                "clang++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-UTARGET_OS_OSX", "-UTARGET_OS_MACCATALYST",
                "-DTARGET_OS_OSX=" + str(is_osx),
                "-DTARGET_OS_MACCATALYST=" + str(catalyst),
                "-D__MAC_OS_X_VERSION_MAX_ALLOWED=" + str(mac_sdk),
                "-D__IPHONE_OS_VERSION_MAX_ALLOWED=" + str(ios_sdk),
                "-D__MAC_OS_X_VERSION_MIN_REQUIRED=" + str(min_version),
                "-x", "c++", "-", "-o", str(output),
            ]
            compiled = subprocess.run(command, input=source_text, text=True,
                                      capture_output=True, check=False)
            if compiled.returncode:
                raise SystemExit(f"{name} compile failed:\n{compiled.stderr}")
            executed = subprocess.run([str(output)], text=True, capture_output=True,
                                      check=False)
            if executed.returncode:
                raise SystemExit(f"{name} policy assertions failed:\n{executed.stderr}")
    print("synthetic native Family 1 math-options selector policy passed (not runtime acceptance)")


if __name__ == "__main__":
    main()
