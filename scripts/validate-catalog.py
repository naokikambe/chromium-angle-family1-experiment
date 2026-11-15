#!/usr/bin/env python3
"""Validate the versioned source and build catalog without third-party packages."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
BASELINE_FIELDS = {"patchset_id", "patch_sha256", "recipe_id", "recipe_sha256"}
CHROME_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
GN_TYPES = {
    "is_debug": bool, "is_component_build": bool, "target_cpu": str,
    "use_system_xcode": bool, "clang_use_chrome_plugins": bool,
    "mac_deployment_target": str, "mac_min_system_version": str,
    "angle_assert_always_on": bool, "angle_enable_metal": bool,
    "angle_enable_gl": bool, "angle_enable_vulkan": bool,
    "angle_enable_swiftshader": bool, "angle_enable_null": bool,
    "angle_enable_wgpu": bool, "angle_enable_cl": bool,
    "angle_build_tests": bool, "build_angle_deqp_tests": bool,
    "symbol_level": int,
}

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.maintenance_angle.inputs import recipe_sha256  # noqa: E402


class CatalogError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CatalogError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"{path}: cannot read JSON: {exc}") from exc
    require(isinstance(value, dict), f"{path}: expected JSON object")
    require(value.get("schema_version") == 1, f"{path}: unsupported schema_version")
    return value


def validate_catalog(root: Path) -> None:
    chrome_files = sorted((root / "chrome").glob("*.json"))
    angle_files = sorted((root / "angle-revisions").glob("*.json"))
    patch_files = sorted((root / "patchsets").glob("*.json"))
    recipe_files = sorted((root / "recipes").glob("*.json"))
    require(chrome_files and angle_files and patch_files and recipe_files,
            "catalog is missing a required mapping collection")
    chrome = [load_json(p) for p in chrome_files]
    angles = [load_json(p) for p in angle_files]
    patches = [load_json(p) for p in patch_files]
    recipes = [load_json(p) for p in recipe_files]
    for values, key, label in ((chrome, "chrome_version", "Chrome version"),
                               (angles, "revision", "ANGLE revision"),
                               (patches, "id", "patchset id"),
                               (recipes, "id", "recipe id")):
        ids = [item.get(key) for item in values]
        require(all(isinstance(x, str) and x for x in ids), f"missing {label}")
        require(len(ids) == len(set(ids)), f"duplicate {label}")
    chrome_by_version = {x["chrome_version"]: x for x in chrome}
    angle_by_revision = {x["revision"]: x for x in angles}
    patch_by_id = {x["id"]: x for x in patches}
    recipe_by_id = {x["id"]: x for x in recipes}
    for item in chrome:
        version = item["chrome_version"]
        require(bool(CHROME_VERSION.fullmatch(version)), f"malformed Chrome version: {version}")
        require(item.get("kind") == "chrome_source", "invalid Chrome source kind")
        require(bool(HEX40.fullmatch(str(item.get("chromium_revision", "")))), "malformed Chromium revision")
        angle_ref = item.get("angle_revision")
        require(bool(HEX40.fullmatch(str(angle_ref))) and angle_ref in angle_by_revision,
                f"missing or malformed ANGLE mapping for Chrome {version}")
        binding = item.get("baseline_inputs")
        require(isinstance(binding, dict) and set(binding) == BASELINE_FIELDS,
                f"Chrome {version} has no complete fixed baseline input binding")
        require(isinstance(binding["patchset_id"], str) and binding["patchset_id"],
                f"Chrome {version} has a malformed baseline patchset ID")
        require(isinstance(binding["recipe_id"], str) and binding["recipe_id"],
                f"Chrome {version} has a malformed baseline recipe ID")
        require(bool(HEX64.fullmatch(str(binding["patch_sha256"]))) and
                bool(HEX64.fullmatch(str(binding["recipe_sha256"]))),
                f"Chrome {version} has a malformed baseline input hash")
    for item in angles:
        require(item.get("kind") == "angle_source", "invalid ANGLE source kind")
        require(bool(HEX40.fullmatch(str(item.get("revision", "")))), "malformed ANGLE revision")
    for item in patches:
        require(item.get("kind") == "patchset", "invalid patchset kind")
        require(item.get("angle_revision") in angle_by_revision, "patchset references unsupported ANGLE revision")
        require(bool(HEX64.fullmatch(str(item.get("patch_sha256", "")))), "malformed patch SHA-256")
        apply_order = item.get("apply_order")
        blobs = item.get("source_blobs")
        require(isinstance(apply_order, list) and apply_order and all(isinstance(x, str) for x in apply_order),
                "invalid patch apply order")
        require(len(apply_order) == len(set(apply_order)), "duplicate patch apply-order path")
        require(isinstance(blobs, dict) and set(blobs) == set(apply_order),
                "source blob mappings do not match patch apply order")
        require(all(isinstance(v, str) and bool(HEX40.fullmatch(v)) for v in blobs.values()),
                "malformed source blob ID")
        patch_path = Path(str(item.get("patch_path", "")))
        require(not patch_path.is_absolute() and ".." not in patch_path.parts, "unsafe patch path")
        actual_path = root.parent / patch_path
        require(actual_path.is_file(), f"patch file is missing: {patch_path}")
        patch_bytes = actual_path.read_bytes()
        actual_sha = hashlib.sha256(patch_bytes).hexdigest()
        require(actual_sha == item["patch_sha256"], "patch hash does not match catalog")
        try:
            patch_text = patch_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CatalogError("patch file is not UTF-8 text") from exc
        diff_paths = []
        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                match = re.fullmatch(r"diff --git a/(.+) b/(.+)", line)
                require(match is not None, "malformed patch diff header")
                require(match.group(1) == match.group(2), "patch diff paths differ")
                diff_paths.append(match.group(2))
        require(diff_paths == apply_order, "patch apply order does not match ordered diff paths")
    require(sum(item.get("candidate_for_new_angle") is True for item in patches) == 1,
            "catalog must identify exactly one reviewed patchset for unlisted ANGLE candidates")
    for item in recipes:
        require(item.get("kind") == "build_recipe", "invalid build recipe kind")
        require(item.get("chrome_source") in chrome_by_version, "recipe references unsupported Chrome source")
        require(item.get("patchset") in patch_by_id, "recipe references unsupported patchset")
        require(item.get("angle_revision") in angle_by_revision, "recipe references unsupported ANGLE revision")
        source = chrome_by_version[item["chrome_source"]]
        patch = patch_by_id[item["patchset"]]
        require(source["angle_revision"] == item["angle_revision"] == patch["angle_revision"],
                "recipe source/patch ANGLE mappings disagree")
        require(item.get("depot_tools_revision") and bool(HEX40.fullmatch(item["depot_tools_revision"])),
                "malformed depot_tools revision")
        require(item.get("architecture") == "x86_64", "unsupported architecture")
        require(isinstance(item.get("ninja_targets"), list) and item["ninja_targets"] == ["libEGL", "libGLESv2"],
                "unsupported or malformed Ninja targets")
        args = item.get("gn_args")
        require(isinstance(args, dict) and set(args) == set(GN_TYPES), "GN arg keys do not match supported recipe")
        for name, expected_type in GN_TYPES.items():
            value = args[name]
            require(type(value) is expected_type, f"invalid GN arg type: {name}")
        require(args["target_cpu"] == "x64" and args["mac_deployment_target"] == item.get("macos_deployment_target"),
                "GN architecture/deployment target disagrees with recipe")
    require(sum(item.get("candidate_default") is True for item in recipes) == 1,
            "catalog must identify exactly one default build recipe")
    default_patch = next(item for item in patches if item.get("candidate_for_new_angle") is True)
    default_recipe = next(item for item in recipes if item.get("candidate_default") is True)
    require(default_recipe.get("patchset") == default_patch["id"] and
            default_recipe.get("angle_revision") == default_patch.get("angle_revision"),
            "candidate default recipe and patchset do not form a consistent pair")
    for item in chrome:
        binding = item["baseline_inputs"]
        patch = patch_by_id.get(binding["patchset_id"])
        recipe = recipe_by_id.get(binding["recipe_id"])
        require(patch is not None, f"Chrome {item['chrome_version']} baseline patchset is missing")
        require(recipe is not None, f"Chrome {item['chrome_version']} baseline recipe is missing")
        require(patch.get("angle_revision") == item["angle_revision"] and
                recipe.get("chrome_source") == item["chrome_version"] and
                recipe.get("angle_revision") == item["angle_revision"] and
                recipe.get("patchset") == patch["id"],
                f"Chrome {item['chrome_version']} baseline source/patch/recipe mapping disagrees")
        require(patch.get("patch_sha256") == binding["patch_sha256"],
                f"Chrome {item['chrome_version']} baseline patch hash disagrees with its patchset")
        recipe_sha = recipe_sha256(recipe)
        require(recipe_sha == binding["recipe_sha256"],
                f"Chrome {item['chrome_version']} baseline recipe hash disagrees with its recipe file")
    # Every declared object must participate in a complete recipe; mappings may grow.
    used_chrome = {item["chrome_source"] for item in recipes}
    used_patches = {item["patchset"] for item in recipes}
    used_angles = {item["angle_revision"] for item in chrome}
    require(used_chrome == set(chrome_by_version), "catalog contains unused Chrome sources")
    require(used_patches == set(patch_by_id), "catalog contains unused patchsets")
    require(used_angles == set(angle_by_revision), "catalog contains unused ANGLE sources")
    require({item["angle_revision"] for item in patches} == set(angle_by_revision),
            "catalog contains ANGLE sources without patch mappings")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", nargs="?", type=Path, default=Path(__file__).resolve().parents[1] / "catalog")
    args = parser.parse_args()
    try:
        validate_catalog(args.catalog.resolve())
    except CatalogError as exc:
        print(f"catalog validation failed: {exc}", file=sys.stderr)
        return 1
    print("catalog validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
