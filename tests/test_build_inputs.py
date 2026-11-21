import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from src.maintenance_angle.inputs import InputError, resolve_inputs, recipe_sha256

ROOT = Path(__file__).resolve().parents[1]
CHROME = "156.0.8078.48"
CHROMIUM = "d0c02bfad08ec92a6ffcf989e53cd995e6381a4c"
ANGLE = "3b89d84e9d59f75675ac4e2bef58fc068a9f0577"
WORKFLOW = "a" * 40
PATCHSET = "metal-family1-v1"
RECIPE = "macos-x64-metal-v1"
PATCH_SHA = "dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0"
CHROME_158 = "158.0.8127.37"
CHROMIUM_158 = "b8c2be851f62f6a394ec57955d7f31335d7cb6d4"
ANGLE_158 = "1f6526a566c27c7c33aa73a78517450a4a2a1714"
PATCHSET_158 = "metal-family1-158-v1"
RECIPE_158 = "macos-x64-metal-158-v1"
PATCH_SHA_158 = "5a3956dbc6428cc6afe610b09a99d4eeaadedb6b8ac396e8e6ccd670a2983def"


class BuildInputTests(unittest.TestCase):
    def copy_catalog(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        temp = tempfile.TemporaryDirectory()
        base = Path(temp.name)
        shutil.copytree(ROOT / "catalog", base / "catalog")
        shutil.copytree(ROOT / "patches", base / "patches")
        self.addCleanup(temp.cleanup)
        return temp, base / "catalog"

    def resolve_known(self, catalog: Path, **kwargs):
        return resolve_inputs(catalog, CHROME, CHROMIUM, ANGLE, WORKFLOW, **kwargs)

    def test_known_156_mapping_checks_exact_pins_and_fixed_inputs(self):
        result = self.resolve_known(ROOT / "catalog")
        self.assertEqual(result["patch_candidate_status"], "catalog-match")
        self.assertEqual(result["selection_mode"], "catalog-baseline")
        self.assertEqual(result["patchset_id"], PATCHSET)
        self.assertEqual(result["patch_sha256"], PATCH_SHA)
        self.assertEqual(result["recipe_id"], RECIPE)
        self.assertEqual(result["recipe_sha256"], recipe_sha256(result["recipe"]))
        self.assertEqual(result["patch_apply_order"][0], "include/GLSLANG/ShaderLang.h")
        self.assertEqual(result["patch_source_revision"], ANGLE)
        self.assertIsNone(result["patch_expected_shader_api_version"])
        self.assertEqual(result["architecture"], "x86_64")
        self.assertEqual(len(result["build_key"]), 64)
        key_fields = ("schema", "chrome_version", "chromium_revision", "angle_revision", "patchset_id",
                      "patch_sha256", "recipe_id", "recipe_sha256", "selection_mode", "workflow_revision")
        expected_key = hashlib.sha256(json.dumps(
            {key: result[key] for key in key_fields}, sort_keys=True, separators=(",", ":")
        ).encode()).hexdigest()
        self.assertEqual(result["schema"], "angle-build-key-v2")
        self.assertEqual(result["build_key"], expected_key)

    def test_adding_new_default_recipe_does_not_change_156_baseline(self):
        original_baseline = self.resolve_known(ROOT / "catalog")
        _temp, catalog = self.copy_catalog()
        recipe_path = catalog / "recipes/macos-x64-metal-158-v1.json"
        original = json.loads(recipe_path.read_text(encoding="utf-8"))
        original["candidate_default"] = False
        recipe_path.write_text(json.dumps(original, sort_keys=True), encoding="utf-8")
        new_default = copy.deepcopy(original)
        new_default["id"] = "macos-x64-metal-test-v2"
        new_default["candidate_default"] = True
        new_default["gn_args"]["symbol_level"] = 1
        (catalog / "recipes/macos-x64-metal-test-v2.json").write_text(
            json.dumps(new_default, sort_keys=True), encoding="utf-8")
        trial_recipe = json.loads((catalog / "recipes/macos-x64-metal-v1.json").read_text(encoding="utf-8"))
        trial_recipe["id"] = "macos-x64-metal-156-trial"
        trial_recipe["gn_args"]["symbol_level"] = 1
        (catalog / "recipes/macos-x64-metal-156-trial.json").write_text(
            json.dumps(trial_recipe, sort_keys=True), encoding="utf-8")

        from tests.test_catalog import validator
        validator.validate_catalog(catalog)

        known = self.resolve_known(catalog)
        self.assertEqual(known["recipe_id"], RECIPE)
        self.assertEqual(known["recipe"]["gn_args"]["symbol_level"], 0)
        self.assertEqual(known["recipe_sha256"], original_baseline["recipe_sha256"])
        self.assertEqual(known["build_key"], original_baseline["build_key"])

        unknown = resolve_inputs(catalog, "157.0.300.2", "f" * 40, "e" * 40, "c" * 40)
        self.assertEqual(unknown["selection_mode"], "new-revision-candidate")
        self.assertEqual(unknown["recipe_id"], "macos-x64-metal-test-v2")
        self.assertEqual(unknown["recipe"]["gn_args"]["symbol_level"], 1)

        trial = self.resolve_known(catalog, patchset_id=PATCHSET, recipe_id="macos-x64-metal-156-trial")
        self.assertEqual(trial["selection_mode"], "explicit-known-version-trial")
        self.assertNotEqual(trial["build_key"], known["build_key"])

    def test_adding_new_default_patchset_does_not_change_156_baseline(self):
        original_baseline = self.resolve_known(ROOT / "catalog")
        _temp, catalog = self.copy_catalog()
        patch_path = catalog / "patchsets/metal-family1-158-v1.json"
        original_patch = json.loads(patch_path.read_text(encoding="utf-8"))
        original_patch["candidate_for_new_angle"] = False
        patch_path.write_text(json.dumps(original_patch, sort_keys=True), encoding="utf-8")

        new_patch = copy.deepcopy(original_patch)
        new_patch["id"] = "metal-family1-158-test-v2"
        new_patch["candidate_for_new_angle"] = True
        (catalog / "patchsets/metal-family1-158-test-v2.json").write_text(
            json.dumps(new_patch, sort_keys=True), encoding="utf-8")

        old_recipe_path = catalog / "recipes/macos-x64-metal-158-v1.json"
        original_recipe = json.loads(old_recipe_path.read_text(encoding="utf-8"))
        original_recipe["candidate_default"] = False
        old_recipe_path.write_text(json.dumps(original_recipe, sort_keys=True), encoding="utf-8")
        new_recipe = copy.deepcopy(original_recipe)
        new_recipe["id"] = "macos-x64-metal-158-test-v2"
        new_recipe["candidate_default"] = True
        new_recipe["patchset"] = "metal-family1-158-test-v2"
        (catalog / "recipes/macos-x64-metal-158-test-v2.json").write_text(
            json.dumps(new_recipe, sort_keys=True), encoding="utf-8")

        from tests.test_catalog import validator
        validator.validate_catalog(catalog)

        known = self.resolve_known(catalog)
        self.assertEqual(known["patchset_id"], PATCHSET)
        self.assertEqual(known["patch_sha256"], PATCH_SHA)
        self.assertEqual(known["recipe_id"], RECIPE)
        self.assertEqual(known["build_key"], original_baseline["build_key"])

        unknown = resolve_inputs(catalog, "157.0.300.2", "f" * 40, "e" * 40, "c" * 40)
        self.assertEqual(unknown["patchset_id"], "metal-family1-158-test-v2")
        self.assertEqual(unknown["recipe_id"], "macos-x64-metal-158-test-v2")
        self.assertEqual(unknown["patch_sha256"], PATCH_SHA_158)

    def test_exact_158_candidate_pins_hashes_and_selection_mode(self):
        result = resolve_inputs(ROOT / "catalog", CHROME_158, CHROMIUM_158, ANGLE_158, WORKFLOW)
        self.assertEqual(result["patch_candidate_status"], "unlisted-revision-candidate")
        self.assertEqual(result["selection_mode"], "new-revision-candidate")
        self.assertEqual(result["patchset_id"], PATCHSET_158)
        self.assertEqual(result["patch_sha256"], PATCH_SHA_158)
        self.assertEqual(result["recipe_id"], RECIPE_158)
        self.assertEqual(result["recipe_sha256"], recipe_sha256(result["recipe"]))
        self.assertEqual(result["patch_source_revision"], ANGLE_158)
        self.assertEqual(result["patch_expected_shader_api_version"], 427)
        self.assertEqual(result["patch_apply_order"], [
            "include/GLSLANG/ShaderLang.h",
            "src/common/apple_platform_utils.mm",
            "src/compiler/translator/msl/EmitMetal.cpp",
            "src/libANGLE/renderer/metal/ShaderMtl.mm",
            "src/libANGLE/renderer/metal/mtl_utils.mm",
        ])
        with self.assertRaisesRegex(InputError, "candidate Chrome source mapping disagrees"):
            resolve_inputs(ROOT / "catalog", CHROME_158, "a" * 40, ANGLE_158, WORKFLOW)
        with self.assertRaisesRegex(InputError, "candidate Chrome source mapping disagrees"):
            resolve_inputs(ROOT / "catalog", CHROME_158, CHROMIUM_158, "e" * 40, WORKFLOW)

    def test_unknown_chrome_and_angle_use_explicit_candidate_defaults(self):
        result = resolve_inputs(ROOT / "catalog", "157.0.300.2", "a" * 40, "b" * 40, "c" * 40)
        self.assertEqual(result["patch_candidate_status"], "unlisted-revision-candidate")
        self.assertEqual(result["selection_mode"], "new-revision-candidate")
        self.assertEqual(result["angle_revision"], "b" * 40)
        self.assertEqual(result["patchset_id"], PATCHSET_158)
        self.assertTrue(result["recipe"]["candidate_default"])
        self.assertEqual(result["recipe_id"], RECIPE_158)
        changed_source = resolve_inputs(ROOT / "catalog", "157.0.300.2", "d" * 40, "e" * 40, "c" * 40)
        self.assertNotEqual(changed_source["build_key"], result["build_key"])

    def test_unlisted_ambiguous_defaults_and_partial_explicit_selection_fail_closed(self):
        _temp, catalog = self.copy_catalog()
        patch = json.loads((catalog / "patchsets/metal-family1-158-v1.json").read_text(encoding="utf-8"))
        patch["id"] = "metal-family1-158-extra"
        (catalog / "patchsets/metal-family1-158-extra.json").write_text(json.dumps(patch), encoding="utf-8")
        with self.assertRaisesRegex(InputError, "exactly one candidate patchset"):
            resolve_inputs(catalog, "157.0.300.2", "a" * 40, "b" * 40, WORKFLOW)
        with self.assertRaisesRegex(InputError, "both patchset and recipe"):
            self.resolve_known(catalog, patchset_id=PATCHSET)

    def test_known_mapping_missing_ambiguous_or_conflicting_fails_closed(self):
        cases = ("missing binding", "missing patchset", "ambiguous Chrome mapping",
                 "ambiguous ANGLE mapping", "conflicting recipe pair")
        for case in cases:
            with self.subTest(case=case):
                _temp, catalog = self.copy_catalog()
                chrome_path = catalog / "chrome/156.0.8078.48.json"
                chrome = json.loads(chrome_path.read_text(encoding="utf-8"))
                if case == "missing binding":
                    chrome.pop("baseline_inputs")
                    chrome_path.write_text(json.dumps(chrome), encoding="utf-8")
                elif case == "missing patchset":
                    chrome["baseline_inputs"]["patchset_id"] = "not-registered"
                    chrome_path.write_text(json.dumps(chrome), encoding="utf-8")
                elif case == "ambiguous Chrome mapping":
                    (catalog / "chrome/duplicate.json").write_text(json.dumps(chrome), encoding="utf-8")
                elif case == "ambiguous ANGLE mapping":
                    angle_path = catalog / f"angle-revisions/{ANGLE}.json"
                    (catalog / "angle-revisions/duplicate.json").write_text(
                        angle_path.read_text(encoding="utf-8"), encoding="utf-8")
                elif case == "conflicting recipe pair":
                    recipe_path = catalog / "recipes/macos-x64-metal-v1.json"
                    recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
                    recipe["patchset"] = "not-registered"
                    recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
                with self.assertRaises(InputError):
                    self.resolve_known(catalog)

    def test_known_source_pin_mismatch_fails_closed(self):
        with self.assertRaises(InputError):
            resolve_inputs(ROOT / "catalog", CHROME, "a" * 40, "b" * 40, WORKFLOW)


if __name__ == "__main__":
    unittest.main()
