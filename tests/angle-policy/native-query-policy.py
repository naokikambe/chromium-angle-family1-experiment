#!/usr/bin/env python3
"""Compile a synthetic harness around the actual patched Mac-family helper."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import sys


def extract_helper(source: str) -> str:
    signature = "bool SupportsMacGPUFamily(id<MTLDevice> device, uint8_t macFamily)"
    start = source.index(signature)
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                helper = source[start : index + 1]
                helper = helper.replace(signature, "bool SupportsMacGPUFamily(Device* device, uint8_t macFamily)")
                helper = re.sub(
                    r"\[device supportsFamily:(MTLGPUFamily\w+)\]",
                    r"device->supportsFamily(\1)",
                    helper,
                )
                if "[device supportsFamily:" in helper:
                    raise ValueError("unconverted Objective-C device query remains")
                return helper
    raise ValueError("unbalanced SupportsMacGPUFamily body")


PRELUDE = r"""#include <cstdint>
#include <cstdio>
#include <string>

static std::string gEnvironment;
namespace angle {
std::string GetEnvironmentVar(const char*) { return gEnvironment; }
}

enum MetalFamily {
  MTLGPUFamilyMac1 = 1,
  MTLGPUFamilyMac2 = 2,
  MTLGPUFamilyMacCatalyst1 = 3,
  MTLGPUFamilyMacCatalyst2 = 4,
};
struct Device {
  bool mac1;
  bool mac2;
  bool catalyst1;
  bool catalyst2;
  bool supportsFamily(MetalFamily family) {
    switch (family) {
      case MTLGPUFamilyMac1: return mac1;
      case MTLGPUFamilyMac2: return mac2;
      case MTLGPUFamilyMacCatalyst1: return catalyst1;
      case MTLGPUFamilyMacCatalyst2: return catalyst2;
    }
    return false;
  }
};
"""


MAIN = r"""
static bool Check(bool actual, bool expected, const char* name) {
  if (actual == expected) return true;
  std::fprintf(stderr, "policy case failed: %s expected=%d actual=%d\n", name,
               expected, actual);
  return false;
}

int main() {
  bool ok = true;
#if TARGET_OS_MACCATALYST && __IPHONE_OS_VERSION_MIN_REQUIRED < 160000
  gEnvironment = "1";
  Device device{true, false, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "Catalyst pre-16 ignores native Mac1 opt-in");
  device = Device{false, false, true, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), true,
              "Catalyst pre-16 retains Catalyst1 query");
  device = Device{false, false, false, true};
  ok &= Check(SupportsMacGPUFamily(&device, 2), true,
              "Catalyst pre-16 retains Catalyst2 query");
#elif TARGET_OS_MACCATALYST
  gEnvironment = "1";
  Device device{true, false, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "Catalyst 16+ keeps deployment fallback");
  device = Device{false, true, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), true,
              "Catalyst 16+ keeps Mac2 fallback");
#elif TARGET_OS_OSX && __MAC_OS_X_VERSION_MIN_REQUIRED < 130000
  gEnvironment = "";
  Device device{true, false, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), true,
              "pre-13 default keeps native Mac1 query");
  device = Device{false, true, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 2), true,
              "pre-13 case2 remains Mac2 query");
#elif TARGET_OS_OSX
  Device device{true, false, false, false};
  gEnvironment = "";
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "unset opt-in retains macOS 13 mapping");
  gEnvironment = "true";
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "invalid opt-in retains macOS 13 mapping");
  gEnvironment = "0";
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "zero opt-in retains macOS 13 mapping");
  gEnvironment = "1";
  ok &= Check(SupportsMacGPUFamily(&device, 1), true,
              "exact opt-in recognizes native Mac1-only");
  ok &= Check(SupportsMacGPUFamily(&device, 2), false,
              "case2 remains Mac2 query on Mac1-only device");
  device = Device{true, true, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), true,
              "Mac2 device retains original family1 query");
  ok &= Check(SupportsMacGPUFamily(&device, 2), true,
              "Mac2 case2 result remains unchanged");
  device = Device{false, false, false, false};
  ok &= Check(SupportsMacGPUFamily(&device, 1), false,
              "opt-in does not invent family support");
#endif
  return ok ? 0 : 1;
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mtl-utils", required=True, type=Path)
    args = parser.parse_args()
    compiler = shutil.which("clang++")
    if compiler is None:
        print("clang++ is required for the synthetic policy harness", file=sys.stderr)
        return 1

    try:
        helper = extract_helper(args.mtl_utils.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"native Mac-family source audit failed: {error}", file=sys.stderr)
        return 1

    variants = (
        ("macos12", ("TARGET_OS_OSX=1", "TARGET_OS_MACCATALYST=0", "__MAC_OS_X_VERSION_MIN_REQUIRED=120000", "__IPHONE_OS_VERSION_MIN_REQUIRED=150000")),
        ("macos13", ("TARGET_OS_OSX=1", "TARGET_OS_MACCATALYST=0", "__MAC_OS_X_VERSION_MIN_REQUIRED=130000", "__IPHONE_OS_VERSION_MIN_REQUIRED=160000")),
        ("catalyst15", ("TARGET_OS_OSX=0", "TARGET_OS_MACCATALYST=1", "__MAC_OS_X_VERSION_MIN_REQUIRED=130000", "__IPHONE_OS_VERSION_MIN_REQUIRED=150000")),
        ("catalyst16", ("TARGET_OS_OSX=0", "TARGET_OS_MACCATALYST=1", "__MAC_OS_X_VERSION_MIN_REQUIRED=130000", "__IPHONE_OS_VERSION_MIN_REQUIRED=160000")),
    )
    with tempfile.TemporaryDirectory(prefix="phase5-family-policy-") as temp_dir:
        root = Path(temp_dir)
        for name, definitions in variants:
            source = root / f"{name}.cc"
            binary = root / name
            source.write_text(PRELUDE + helper + MAIN, encoding="utf-8")
            command = [compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror"]
            command.extend(("-UTARGET_OS_OSX", "-UTARGET_OS_MACCATALYST"))
            command.extend(f"-D{definition}" for definition in definitions)
            command.extend((str(source), "-o", str(binary)))
            compiled = subprocess.run(command, capture_output=True, text=True, check=False)
            if compiled.returncode:
                print(f"{name} compile failed:\n{compiled.stderr}", file=sys.stderr)
                return 1
            executed = subprocess.run((str(binary),), capture_output=True, text=True, check=False)
            if executed.returncode:
                print(f"{name} policy failed:\n{executed.stderr}", file=sys.stderr)
                return 1

    print("native Mac-family policy: extracted helper passed macOS 12/13 and Catalyst 15/16 synthetic harnesses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
