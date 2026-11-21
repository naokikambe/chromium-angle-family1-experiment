"""Resolve exact baseline bindings or reviewed defaults for new ANGLE candidates."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .chromium import REVISION_RE
from .stable import VERSION_RE

HEX64 = set("0123456789abcdef")
BASELINE_FIELDS = {"patchset_id", "patch_sha256", "recipe_id", "recipe_sha256"}


class InputError(ValueError):
    pass


def recipe_sha256(recipe: dict[str, Any]) -> str:
    """Hash the canonical build recipe, excluding only its default-selection flag.

    ``candidate_default`` selects the recipe for unregistered releases; it does
    not affect the build. Excluding it keeps a fixed baseline digest stable when
    maintainers designate a different recipe as the new-version default.
    """
    build_recipe = {key: value for key, value in recipe.items() if key != "candidate_default"}
    encoded = json.dumps(build_recipe, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError(f"cannot read catalog entry: {path.name}") from exc
    if not isinstance(value, dict):
        raise InputError(f"catalog entry is not an object: {path.name}")
    return value


def _exact_entry(entries: list[dict[str, Any]], identifier: str, label: str) -> dict[str, Any]:
    matches = [entry for entry in entries if entry.get("id") == identifier]
    if len(matches) != 1:
        raise InputError(f"{label} selection is missing or ambiguous: {identifier}")
    return matches[0]


def _sha256(path: Path, *, boundary: Path, label: str) -> str:
    try:
        if path.is_symlink():
            raise InputError(f"{label} file cannot be a symlink")
        resolved = path.resolve(strict=True)
        resolved.relative_to(boundary.resolve(strict=True))
        if not resolved.is_file():
            raise InputError(f"{label} file is unavailable")
        return hashlib.sha256(resolved.read_bytes()).hexdigest()
    except (OSError, ValueError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"{label} file is unavailable or outside the catalog boundary") from exc


def _validate_pair(patch: dict[str, Any], recipe: dict[str, Any], *,
                   chrome_version: str, angle_revision: str, known_version: bool) -> None:
    patch_id = patch.get("id")
    if patch.get("kind") != "patchset" or not isinstance(patch_id, str) or not patch_id:
        raise InputError("selected patchset is malformed")
    recipe_id = recipe.get("id")
    if recipe.get("kind") != "build_recipe" or not isinstance(recipe_id, str) or not recipe_id:
        raise InputError("selected recipe is malformed")
    if recipe.get("patchset") != patch_id or recipe.get("angle_revision") != patch.get("angle_revision"):
        raise InputError("selected recipe and patchset do not form a consistent catalog pair")
    if known_version and (patch.get("angle_revision") != angle_revision or
                          recipe.get("chrome_source") != chrome_version or
                          recipe.get("angle_revision") != angle_revision):
        raise InputError("known Chrome baseline patch/recipe disagrees with its exact ANGLE source mapping")


def resolve_inputs(root: Path, chrome_version: str, chromium_revision: str,
                   angle_revision: str, workflow_revision: str, *,
                   patchset_id: str | None = None, recipe_id: str | None = None) -> dict[str, Any]:
    """Resolve a registered Chrome baseline or the single reviewed new-version defaults.

    Registered Chrome versions are bound to exact patch/recipe IDs and hashes in
    their Chrome catalog records. Unregistered versions use the unique candidate
    patchset and default recipe. An explicit pair is classified as a trial.
    """
    if not VERSION_RE.fullmatch(chrome_version):
        raise InputError("malformed Chrome version")
    if not REVISION_RE.fullmatch(chromium_revision) or not REVISION_RE.fullmatch(angle_revision):
        raise InputError("Chromium and ANGLE revisions must be full 40-character pins")
    if not REVISION_RE.fullmatch(workflow_revision):
        raise InputError("workflow revision must be a full commit SHA")
    if (patchset_id is None) != (recipe_id is None):
        raise InputError("an explicit input trial must select both patchset and recipe IDs")

    root = root.resolve(strict=True)
    chrome_files = sorted((root / "chrome").glob("*.json"))
    angle_files = sorted((root / "angle-revisions").glob("*.json"))
    patch_files = sorted((root / "patchsets").glob("*.json"))
    recipe_files = sorted((root / "recipes").glob("*.json"))
    chrome_entries = [_read(path) for path in chrome_files]
    angle_entries = [_read(path) for path in angle_files]
    patch_entries = [_read(path) for path in patch_files]
    recipe_entries = [_read(path) for path in recipe_files]
    if not chrome_entries or not angle_files or not patch_entries or not recipe_entries:
        raise InputError("catalog is incomplete")

    chrome_matches = [entry for entry in chrome_entries if entry.get("chrome_version") == chrome_version]
    if len(chrome_matches) > 1:
        raise InputError("known Chrome source mapping is ambiguous")
    chrome_source_match = chrome_matches[0] if chrome_matches else None
    if chrome_source_match is not None and type(chrome_source_match.get("candidate_only", False)) is not bool:
        raise InputError("Chrome source mapping has a malformed source role")
    candidate_source_match = chrome_source_match if chrome_source_match and chrome_source_match.get("candidate_only") else None
    chrome_match = chrome_source_match if chrome_source_match and not chrome_source_match.get("candidate_only") else None
    if chrome_match and (chrome_match.get("chromium_revision") != chromium_revision or
                         chrome_match.get("angle_revision") != angle_revision):
        raise InputError("known Chrome catalog entry disagrees with resolved Chromium tag or DEPS")
    if candidate_source_match and (candidate_source_match.get("chromium_revision") != chromium_revision or
                                   candidate_source_match.get("angle_revision") != angle_revision):
        raise InputError("candidate Chrome source mapping disagrees with resolved Chromium tag or DEPS")
    if candidate_source_match and "baseline_inputs" in candidate_source_match:
        raise InputError("candidate-only Chrome source mapping cannot define a fixed baseline")
    if chrome_match:
        angle_matches = [entry for entry in angle_entries if entry.get("revision") == angle_revision]
        if len(angle_matches) != 1 or angle_matches[0].get("kind") != "angle_source":
            raise InputError("known Chrome mapping has a missing or ambiguous ANGLE source record")
    if candidate_source_match:
        angle_matches = [entry for entry in angle_entries if entry.get("revision") == angle_revision]
        if len(angle_matches) != 1 or angle_matches[0].get("kind") != "angle_source":
            raise InputError("candidate Chrome mapping has a missing or ambiguous ANGLE source record")

    # Reject duplicate IDs rather than allowing sort order or the last file to win.
    for entries, key, label in ((patch_entries, "id", "patchset"),
                                (recipe_entries, "id", "recipe")):
        identifiers = [entry.get(key) for entry in entries]
        if any(not isinstance(value, str) or not value for value in identifiers):
            raise InputError(f"catalog contains a malformed {label} ID")
        if len(identifiers) != len(set(identifiers)):
            raise InputError(f"catalog contains duplicate {label} IDs")

    patch_file_by_id = {entry["id"]: path for entry, path in zip(patch_entries, patch_files)}
    recipe_file_by_id = {entry["id"]: path for entry, path in zip(recipe_entries, recipe_files)}
    catalog_boundary = root.parent.resolve(strict=True)

    def selected_hashes(patch: dict[str, Any], recipe: dict[str, Any]) -> tuple[str, str]:
        raw_patch_path = Path(str(patch.get("patch_path", "")))
        if raw_patch_path.is_absolute() or ".." in raw_patch_path.parts:
            raise InputError("selected patch path is unsafe")
        patch_hash = _sha256(catalog_boundary / raw_patch_path, boundary=catalog_boundary, label="patchset")
        recipe_file = recipe_file_by_id.get(recipe["id"])
        if recipe_file is None:
            raise InputError("selected recipe file is unavailable")
        _sha256(recipe_file, boundary=root / "recipes", label="recipe")
        if _read(recipe_file) != recipe:
            raise InputError("selected recipe changed while resolving inputs")
        recipe_hash = recipe_sha256(recipe)
        if patch_hash != patch.get("patch_sha256"):
            raise InputError("selected patch file hash does not match its catalog entry")
        return patch_hash, recipe_hash

    if chrome_match is not None:
        binding = chrome_match.get("baseline_inputs")
        if not isinstance(binding, dict) or set(binding) != BASELINE_FIELDS:
            raise InputError("known Chrome mapping has no complete fixed baseline input binding")
        for field in ("patch_sha256", "recipe_sha256"):
            value = binding.get(field)
            if not isinstance(value, str) or len(value) != 64 or any(char not in HEX64 for char in value):
                raise InputError(f"known Chrome baseline has a malformed {field}")
        bound_patch = _exact_entry(patch_entries, binding["patchset_id"], "baseline patchset")
        bound_recipe = _exact_entry(recipe_entries, binding["recipe_id"], "baseline recipe")
        _validate_pair(bound_patch, bound_recipe, chrome_version=chrome_version,
                       angle_revision=angle_revision, known_version=True)
        bound_patch_hash, bound_recipe_hash = selected_hashes(bound_patch, bound_recipe)
        if bound_patch_hash != binding["patch_sha256"] or bound_recipe_hash != binding["recipe_sha256"]:
            raise InputError("known Chrome baseline patch/recipe hash differs from its fixed binding")

    if patchset_id is not None:
        patch = _exact_entry(patch_entries, patchset_id, "explicit patchset")
        recipe = _exact_entry(recipe_entries, recipe_id or "", "explicit recipe")
        _validate_pair(patch, recipe, chrome_version=chrome_version, angle_revision=angle_revision,
                       known_version=chrome_match is not None)
        selection_mode = "explicit-known-version-trial" if chrome_match else "explicit-unlisted-revision-trial"
    elif chrome_match is not None:
        binding = chrome_match["baseline_inputs"]
        patch = _exact_entry(patch_entries, binding["patchset_id"], "baseline patchset")
        recipe = _exact_entry(recipe_entries, binding["recipe_id"], "baseline recipe")
        selection_mode = "catalog-baseline"
    else:
        candidate_patches = [item for item in patch_entries if item.get("candidate_for_new_angle") is True]
        default_recipes = [item for item in recipe_entries if item.get("candidate_default") is True]
        if len(candidate_patches) != 1 or len(default_recipes) != 1:
            raise InputError("unlisted revisions require exactly one candidate patchset and one default recipe")
        patch, recipe = candidate_patches[0], default_recipes[0]
        recipe_sources = [entry for entry in chrome_entries
                          if entry.get("chrome_version") == recipe.get("chrome_source")]
        if (len(recipe_sources) != 1 or recipe_sources[0].get("candidate_only") is not True or
                "baseline_inputs" in recipe_sources[0]):
            raise InputError("candidate default recipe must reference a separate candidate-only source mapping")
        _validate_pair(patch, recipe, chrome_version=chrome_version,
                       angle_revision=angle_revision, known_version=False)
        selection_mode = "new-revision-candidate"

    patch_hash, recipe_hash = selected_hashes(patch, recipe)
    key_payload = {
        "schema": "angle-build-key-v2",
        "chrome_version": chrome_version,
        "chromium_revision": chromium_revision,
        "angle_revision": angle_revision,
        "patchset_id": patch["id"],
        "patch_sha256": patch_hash,
        "recipe_id": recipe["id"],
        "recipe_sha256": recipe_hash,
        "selection_mode": selection_mode,
        "workflow_revision": workflow_revision,
    }
    build_key = hashlib.sha256(json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        **key_payload,
        "build_key": build_key,
        "patch_path": patch["patch_path"],
        "patch_apply_order": patch["apply_order"],
        "patch_source_blobs": patch["source_blobs"],
        "patch_source_revision": patch["angle_revision"],
        "patch_expected_shader_api_version": patch.get("patched_shader_api_version"),
        "patch_candidate_status": "catalog-match" if chrome_match else "unlisted-revision-candidate",
        "recipe": recipe,
        "architecture": recipe["architecture"],
        "runner": recipe["runner"],
    }
