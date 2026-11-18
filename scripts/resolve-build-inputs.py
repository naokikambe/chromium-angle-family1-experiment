#!/usr/bin/env python3
"""Resolve reviewed catalog inputs or a fail-closed new revision candidate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.maintenance_angle.inputs import InputError, resolve_inputs  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome-version", required=True)
    parser.add_argument("--chromium-revision", required=True)
    parser.add_argument("--angle-revision", required=True)
    parser.add_argument("--workflow-revision", required=True)
    parser.add_argument("--catalog", type=Path, default=ROOT / "catalog")
    parser.add_argument("--patchset-id", help="explicit patchset for a separately classified input trial")
    parser.add_argument("--recipe-id", help="explicit recipe for a separately classified input trial")
    parser.add_argument("--expect-patchset-id", help="fail unless the resolver selects this patchset")
    parser.add_argument("--expect-patch-sha256", help="fail unless the resolver selects this patch hash")
    parser.add_argument("--expect-recipe-id", help="fail unless the resolver selects this recipe")
    parser.add_argument("--expect-recipe-sha256", help="fail unless the resolver selects this recipe hash")
    args = parser.parse_args()
    expected = (args.expect_patchset_id, args.expect_patch_sha256,
                args.expect_recipe_id, args.expect_recipe_sha256)
    if any(value is not None for value in expected) and not all(value is not None for value in expected):
        parser.error("all four --expect-* values must be supplied together")
    try:
        result = resolve_inputs(args.catalog.resolve(), args.chrome_version, args.chromium_revision,
                                args.angle_revision, args.workflow_revision,
                                patchset_id=args.patchset_id, recipe_id=args.recipe_id)
        if all(value is not None for value in expected):
            actual = (result["patchset_id"], result["patch_sha256"],
                      result["recipe_id"], result["recipe_sha256"])
            if actual != expected:
                raise InputError("selected patch/recipe differs from the required fixed inputs")
    except InputError as exc:
        print(f"build candidate rejected: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
