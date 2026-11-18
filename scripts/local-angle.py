#!/usr/bin/env python3
"""Manually inspect and prepare an exact-version Chrome ANGLE candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.artifact import ArtifactError  # noqa: E402
from src.maintenance_angle.github_artifacts import GitHubError  # noqa: E402
from src.maintenance_angle.local import (LocalError, create_launcher, fetch_artifact, find_index_record,
                             create_finder_launchers, inspect_app, plan_install, prepare_copy, sign_copy,
                             verify_launcher_script, verify_prepared_app)  # noqa: E402

TEMPLATE = ROOT / "templates/launcher/usage-descriptions.json"


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--app", required=True, type=Path)
    p.add_argument("--runtime-architecture", choices=("x86_64", "arm64"))
    p.set_defaults(func=lambda a: print_json(inspect_app(a.app, a.runtime_architecture)) or 0)

    p = sub.add_parser("match")
    p.add_argument("--repository", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    p.set_defaults(func=lambda a: print_json(find_index_record(a.repository, a.version, a.architecture)[0]) or 0)

    p = sub.add_parser("fetch")
    p.add_argument("--repository", required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--architecture", choices=("x86_64", "arm64"), required=True)
    p.add_argument("--destination", required=True, type=Path)
    p.set_defaults(func=lambda a: print_json(fetch_artifact(a.repository, a.version, a.architecture, a.destination)) or 0)

    p = sub.add_parser("plan")
    p.add_argument("--app", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    p.add_argument("--target-copy", required=True, type=Path)
    p.add_argument("--profile-dir", required=True, type=Path)
    p.add_argument("--runtime-architecture", choices=("x86_64", "arm64"), required=True)
    p.set_defaults(func=lambda a: print_json(plan_install(a.app, a.artifact_dir, a.target_copy, a.profile_dir,
                                                          a.runtime_architecture)) or 0)

    p = sub.add_parser("prepare")
    p.add_argument("--app", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    p.add_argument("--target-copy", required=True, type=Path)
    p.add_argument("--profile-dir", required=True, type=Path)
    p.add_argument("--runtime-architecture", choices=("x86_64", "arm64"), required=True)
    p.set_defaults(func=lambda a: print_json(prepare_copy(a.app, a.artifact_dir, a.target_copy, a.profile_dir,
                                                          a.runtime_architecture)) or 0)

    p = sub.add_parser("launcher")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--profile-dir", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--koov-app-id", required=True)
    p.add_argument("--bluetooth-purpose")
    p.set_defaults(func=lambda a: print_json(create_launcher(a.app_copy, a.profile_dir, a.output, TEMPLATE,
                                                             a.bluetooth_purpose, koov_app_id=a.koov_app_id)) or 0)

    p = sub.add_parser("finder-launchers")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--profile-dir", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--koov-registration-url", required=True)
    p.add_argument("--koov-app-id", required=True)
    p.add_argument("--bundle-id-prefix", required=True)
    p.add_argument("--bluetooth-purpose")
    p.set_defaults(func=lambda a: print_json(create_finder_launchers(
        a.app_copy, a.profile_dir, a.output_dir, TEMPLATE, koov_app_id=a.koov_app_id,
        registration_url=a.koov_registration_url, bundle_id_prefix=a.bundle_id_prefix,
        bluetooth_purpose=a.bluetooth_purpose)) or 0)

    p = sub.add_parser("sign")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    p.add_argument("--receipt", required=True, type=Path)
    p.add_argument("--identity", required=True)
    p.add_argument("--execute", action="store_true", help="perform codesign after review; otherwise print commands only")
    p.set_defaults(func=lambda a: print_json({"commands": sign_copy(a.app_copy, a.artifact_dir, a.identity,
                                                                        a.receipt, execute=a.execute),
                                              "receipt": str(a.receipt.expanduser().absolute()),
                                              "executed": a.execute}) or 0)

    p = sub.add_parser("freeze")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--unfreeze", action="store_true")
    p.add_argument("--receipt", type=Path)
    p.set_defaults(func=freeze)

    p = sub.add_parser("verify")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    p.add_argument("--require-signature", action="store_true")
    p.add_argument("--launcher", type=Path)
    p.add_argument("--profile-dir", type=Path)
    p.add_argument("--receipt", type=Path)
    p.set_defaults(func=lambda a: print_json(verify_prepared_app(a.app_copy, a.artifact_dir,
                                                                 require_signature=a.require_signature,
                                                                 launcher_path=a.launcher,
                                                                 profile_path=a.profile_dir,
                                                                 receipt_path=a.receipt)) or 0)

    p = sub.add_parser("status")
    p.add_argument("--app-copy", required=True, type=Path)
    p.add_argument("--artifact-dir", required=True, type=Path)
    p.add_argument("--launcher", type=Path)
    p.add_argument("--profile-dir", type=Path)
    p.add_argument("--receipt", type=Path)
    p.set_defaults(func=lambda a: print_json(verify_prepared_app(a.app_copy, a.artifact_dir,
                                                                 require_signature=False,
                                                                 launcher_path=a.launcher,
                                                                 profile_path=a.profile_dir,
                                                                 receipt_path=a.receipt)) or 0)

    p = sub.add_parser("rollback-plan")
    p.add_argument("--previous-app", required=True, type=Path)
    p.add_argument("--candidate-app", required=True, type=Path)
    p.set_defaults(func=rollback_plan)

    args = parser.parse_args()
    try:
        return int(args.func(args) or 0)
    except (OSError, ValueError, ArtifactError, GitHubError, LocalError) as exc:
        print(f"local ANGLE operation stopped: {exc}", file=sys.stderr)
        return 2


def freeze(args: argparse.Namespace) -> int:
    app = args.app_copy.expanduser().resolve(strict=True)
    if args.execute:
        verify_prepared_app(app, args.artifact_dir, require_signature=True, receipt_path=args.receipt)
        command = ["/usr/bin/chflags", "-R", "uchg", str(app)]
    else:
        command = ["/usr/bin/chflags", "-R", "nouchg", str(app)]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        raise LocalError("could not change immutable flags; inspect status before retrying")
    print_json({"command": command, "status": "FROZEN" if args.execute else "UNFROZEN"})
    return 0


def rollback_plan(args: argparse.Namespace) -> int:
    previous = args.previous_app.expanduser().resolve(strict=True)
    candidate = args.candidate_app.expanduser().resolve(strict=True)
    print_json({"previous_app": str(previous), "candidate_app": str(candidate),
                "steps": ["close the candidate browser normally", "verify the previous app is still present",
                          "launch the previous app with its original profile", "leave candidate copy and evidence in place until owner decides"],
                "automatic_deletion": False, "automatic_profile_switch": False})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
