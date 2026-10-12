#!/usr/bin/env python3
"""Prepare and execute a role-based first-signing trial on a fresh Chromium copy.

This is an experimental adapter of the pinned upstream role policy, not the
complete upstream packaging/notarization pipeline. See README.md.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys

from probe import app_executable, capture, fresh_dir, macho_files, mac_context, sha256, write_json

REVISION = "82303c21a18acdc256c6264cd2ed0e1588df99d4"
FULL = "runtime,kill,restrict,library"
JIT = "runtime,kill,restrict"
REFERENCE = Path(__file__).resolve().parent / "reference"


def role(name):
    if re.search(r"\((?:Aperitif )?Renderer\)\.app$", name):
        return "renderer"
    if re.search(r"\((?:Aperitif )?GPU\)\.app$", name):
        return "gpu"
    if name.endswith(".framework"):
        return "framework"
    return "application"


def bundles(app):
    result = [app]
    for root, dirs, _ in os.walk(app, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
        result.extend(Path(root) / d for d in dirs if d.endswith((".app", ".framework", ".bundle")))
    return sorted(set(result), key=lambda p: (-len(p.parts), str(p)))


def bundle_main(bundle):
    for info_path in (bundle / "Contents/Info.plist", bundle / "Resources/Info.plist"):
        if info_path.is_file():
            info = plistlib.loads(info_path.read_bytes())
            name = info.get("CFBundleExecutable")
            if name and Path(name).name == name:
                for path in (bundle / "Contents/MacOS" / name, bundle / name):
                    if path.is_file():
                        return path.resolve()
    raise RuntimeError("Cannot identify bundle executable: " + str(bundle))


def unsigned(app, out):
    for index, path in enumerate([app] + macho_files(app)):
        code, text = capture(["/usr/bin/codesign", "-dvvv", str(path)], out / f"unsigned-{index:03d}.txt")
        if code == 0 or "code object is not signed at all" not in text:
            raise RuntimeError("Source must be wholly unsigned; preserve this target: " + str(path))


def validate_links(app):
    app_root = Path(app).resolve(strict=True)
    for root, dirs, files in os.walk(app, followlinks=False):
        for name in dirs + files:
            path = Path(root) / name
            if path.is_symlink():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(app_root):
                    raise RuntimeError("Bundle symlink points outside the source: " + str(path))
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]


def identity_valid(identity, out):
    if not re.fullmatch(r"[0-9A-Fa-f]{40}", identity):
        raise RuntimeError("Supply the Apple Development certificate's 40-character SHA-1 fingerprint")
    code, text = capture(["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"], out / "identities.txt")
    if code != 0 or not any(identity.upper() in line.upper() and '"Apple Development:' in line for line in text.splitlines()):
        raise RuntimeError("The selected Apple Development identity is not currently valid")


def build_commands(app, identity, entitlements):
    containers = bundles(app)
    host_executables = {bundle_main(p) for p in containers}
    steps = []
    for path in macho_files(app):
        if path.resolve() not in host_executables:
            # Dylibs have no hardened-runtime flags; stand-alone programs do.
            with path.open("rb") as stream:
                header = stream.read(16)
            little = header[:4] in (bytes.fromhex("cefaedfe"), bytes.fromhex("cffaedfe"))
            filetype = int.from_bytes(header[12:16], "little" if little else "big")
            if header[:4] in (bytes.fromhex("cafebabe"), bytes.fromhex("bebafeca"), bytes.fromhex("cafebabf"), bytes.fromhex("bfbafeca")):
                raise RuntimeError("This signing adapter requires thin x86_64 Mach-O inputs")
            command = ["/usr/bin/codesign", "--sign", identity, "--timestamp=none"]
            if filetype == 2:  # MH_EXECUTE
                command += ["--options", FULL]
            command += [str(path)]
            steps.append({"target": str(path.relative_to(app)), "role": "standalone", "argv": command})
    for path in containers:
        component_role = role(path.name)
        command = ["/usr/bin/codesign", "--sign", identity, "--timestamp=none"]
        if component_role != "framework":
            command += ["--options", JIT if component_role in ("renderer", "gpu") else FULL]
        template = component_role if component_role in ("renderer", "gpu") else ("application" if path == app else None)
        if template:
            command += ["--entitlements", str(entitlements / (template + ".plist"))]
        command += [str(path)]
        steps.append({"target": str(path.relative_to(app)), "role": component_role, "argv": command})
    return steps


def freeze_files(app):
    result = {}
    for root, dirs, files in os.walk(app, followlinks=False):
        for name in dirs + files:
            path = Path(root) / name
            key = str(path.relative_to(app))
            if path.is_symlink():
                result[key] = "symlink:" + os.readlink(path)
            elif path.is_file():
                result[key] = sha256(path)
        dirs[:] = [d for d in dirs if not (Path(root) / d).is_symlink()]
    return result


def prepare(args):
    mac_context()
    source, executable, info = app_executable(args.source)
    if info.get("CFBundleIdentifier") != "org.chromium.Chromium" or source.name != "Chromium.app":
        raise RuntimeError("This adapter accepts the official unbranded Chromium.app snapshot only")
    validate_links(source)
    revisions = json.loads(Path(args.revisions).read_text())
    if revisions.get("got_revision") != REVISION or str(revisions.get("chromium_revision")) != "1689422":
        raise RuntimeError("REVISIONS does not match the pinned snapshot; update/review policy for another revision")
    if revisions.get("got_angle_revision") != "8efd15f71c27cd0bc2a9cf0074d77e899ca9c448":
        raise RuntimeError("The snapshot's ANGLE revision is unexpected")
    if subprocess.check_output(["/usr/bin/lipo", "-archs", str(executable)], text=True).strip() != "x86_64":
        raise RuntimeError("The trial requires a thin Intel x86_64 snapshot")
    out = fresh_dir(args.out)
    identity_valid(args.identity, out)
    unsigned(source, out)
    app = out / "Chromium.app"
    subprocess.run(["/usr/bin/ditto", str(source), str(app)], check=True)
    validate_links(app)
    entitlements = out / "entitlements"
    entitlements.mkdir()
    mapping = {"application": "app-entitlements.plist", "renderer": "helper-renderer-entitlements.plist", "gpu": "helper-gpu-entitlements.plist"}
    provenance = json.loads((REFERENCE / "provenance.json").read_text())
    expected = {Path(f["path"]).name: f["sha256"] for f in provenance["files"]}
    for label, filename in mapping.items():
        if sha256(REFERENCE / filename) != expected[filename]:
            raise RuntimeError("Pinned entitlement reference was changed")
        values = plistlib.loads((REFERENCE / filename).read_bytes())
        values["com.apple.security.get-task-allow"] = True  # Upstream development-signing behavior.
        (entitlements / (label + ".plist")).write_bytes(plistlib.dumps(values))
    commands = build_commands(app, args.identity, entitlements)
    plan = {"schema": "page-recovery-first-sign-v1", "source": str(source), "app": str(app),
            "identity": args.identity, "chromium_revision": REVISION, "revisions": revisions,
            "freeze": freeze_files(app), "entitlements_hashes": {p.name: sha256(p) for p in entitlements.iterdir()},
            "steps": commands, "status": "prepared"}
    write_json(out / "signing-plan.json", plan)
    print(out / "signing-plan.json")
    print("Prepared a fresh unsigned copy and an inspectable signing plan. Signing has not run.")
    return 0


def execute(args):
    mac_context()
    path = Path(args.plan).resolve(strict=True)
    out = path.parent
    plan = json.loads(path.read_text())
    app = out / "Chromium.app"
    if plan.get("schema") != "page-recovery-first-sign-v1" or plan.get("status") != "prepared" or plan.get("app") != str(app):
        raise RuntimeError("Only a prepared plan in its original directory can execute")
    if app.is_symlink() or freeze_files(app) != plan["freeze"]:
        raise RuntimeError("The assembled app changed after preparation")
    validate_links(app)
    entitlements = out / "entitlements"
    if {p.name: sha256(p) for p in entitlements.iterdir()} != plan["entitlements_hashes"]:
        raise RuntimeError("Entitlements changed after preparation")
    if build_commands(app, plan["identity"], entitlements) != plan["steps"]:
        raise RuntimeError("Signing commands differ from the generated policy")
    identity_valid(plan["identity"], out)
    unsigned(app, out)
    # Exclusive marker persists after failure: no retry or re-sign in place.
    descriptor = os.open(out / "execution-started", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    receipt = {"status": "in-progress", "steps": []}
    write_json(out / "signing-receipt.json", receipt)
    try:
        for index, step in enumerate(plan["steps"]):
            code, _ = capture(step["argv"], out / f"sign-{index:03d}.txt", timeout=120)
            receipt["steps"].append({"target": step["target"], "role": step["role"], "exit": code})
            write_json(out / "signing-receipt.json", receipt)
            if code != 0:
                raise RuntimeError("Signing failed; preserve this copy: " + step["target"])
        code, _ = capture(["/usr/bin/codesign", "--verify", "--deep", "--strict", "--verbose=4", str(app)], out / "deep-verify.txt", timeout=60)
        receipt["verify_exit"] = code
        receipt["after_hashes"] = freeze_files(app)
        if code != 0:
            raise RuntimeError("Strict verification failed; preserve this copy")
        receipt["status"] = "signed-and-verified"
    except Exception as exc:
        receipt["status"], receipt["error"] = "failed-preserved", str(exc)
        raise
    finally:
        write_json(out / "signing-receipt.json", receipt)
    print(app)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare_parser = sub.add_parser("prepare")
    for option in ("source", "revisions", "identity", "out"):
        prepare_parser.add_argument("--" + option, required=True)
    prepare_parser.set_defaults(action=prepare)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--plan", required=True)
    execute_parser.set_defaults(action=execute)
    args = parser.parse_args()
    try:
        return args.action(args)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
