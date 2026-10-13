#!/usr/bin/env python3
"""Focused proposal audit; never builds or runs Chromium or a device app."""
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu-info-source', required=True,
                        help='Unmodified gpu_info_collector.cc from Chromium 82303c21')
    args = parser.parse_args()
    source = Path(args.gpu_info_source).read_bytes()
    if hashlib.sha256(source).hexdigest() != '8bfe8984e4cfa8b4ed3e15d5ae8bf54d03a85fe478cac7466499b31049d06a9d':
        raise ValueError('Source does not match the reviewed exact Chromium revision')
    patch = Path(__file__).resolve().parents[1] / 'patches/phase5-chromium-family1-es2-info-context.patch'
    with tempfile.TemporaryDirectory(prefix='phase5-es2-info-focused-') as directory:
        root = Path(directory)
        target = root / 'gpu/config/gpu_info_collector.cc'
        target.parent.mkdir(parents=True)
        target.write_bytes(source)
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=root, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=root, check=True)
        text = target.read_text()
        assert text.count('attribs.allow_es_version_fallback = true;') == 1
        assert '#if BUILDFLAG(IS_MAC)\n  // Only the explicit Family 1' in text
        assert '!features::ShouldFallbackToSWIfGLES3NotSupported();' in text
        condition = re.search(r'  if \((family1_opt_in.*?)\) \{\n    attribs.allow_es_version_fallback = true;', text, re.S).group(1)
        fixture = r'''
#include <map>
#include <optional>
#include <string>
namespace switches {
const char kUseGL[]="use-gl", kUseANGLE[]="use-angle";
const char kUseDynamicAngle[]="use-dynamic-angle";
const char kDisableANGLEFeatures[]="disable-angle-features";
}
struct CommandLine {
std::map<std::string,std::string> values;
std::string GetSwitchValueASCII(const char* name) const {
auto item=values.find(name); return item==values.end()?"":item->second;
}
bool HasSwitch(const char* name) const { return values.count(name); }
};
bool enabled(std::optional<std::string> family1_opt_in, const CommandLine* command_line) {
return CONDITION;
}
int main() {
CommandLine cmd{{{"use-gl","angle"},{"use-angle","metal"},{"use-dynamic-angle",""},{"disable-angle-features","requireGpuFamily2"}}};
if(!enabled("1",&cmd))return 1;
for(auto value: {std::optional<std::string>(),std::optional<std::string>(""),std::optional<std::string>("0"),std::optional<std::string>("true")})if(enabled(value,&cmd))return 2;
for(auto key:{"use-gl","use-angle","use-dynamic-angle","disable-angle-features"}) {
auto missing=cmd;missing.values.erase(key);if(enabled("1",&missing))return 3;
}
for(auto key:{"use-gl","use-angle","disable-angle-features"}) {
auto wrong=cmd;wrong.values[key]="unreviewed";if(enabled("1",&wrong))return 4;
}
return 0;
}
'''.replace('CONDITION', condition)
        cpp = root / 'opt-in-policy.cc'
        cpp.write_text(fixture)
        executable = root / 'opt-in-policy'
        subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    print('PATCH_APPLY_AND_OPT_IN_POLICY_PASS; CHROMIUM_NOT_COMPILED; DEVICE_NOT_RUN')


if __name__ == '__main__':
    main()
