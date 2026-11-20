import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("validate_catalog", ROOT / "scripts/validate-catalog.py")
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class CatalogTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory()
        base = Path(temp.name)
        catalog = base / "catalog"
        for folder in ("chrome", "angle-revisions", "patchsets", "recipes"):
            (catalog / folder).mkdir(parents=True)
        patch_path = base / "patches" / "fixture.patch"
        patch_path.parent.mkdir()
        patch_path.write_bytes(b"diff --git a/src/file.cc b/src/file.cc\nsynthetic patch fixture\n")
        revision = "a" * 40
        candidate_revision = "e" * 40
        blob_map = {"src/file.cc": "b" * 40}
        patch = {"schema_version": 1, "kind": "patchset", "id": "fixture",
                 "candidate_for_new_angle": False, "angle_revision": revision,
                 "patch_path": "patches/fixture.patch",
                 "patch_sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                 "apply_order": list(blob_map), "source_blobs": blob_map}
        recipe = {"schema_version": 1, "kind": "build_recipe", "id": "fixture",
                  "candidate_default": False, "chrome_source": "1.2.300.4",
                  "angle_revision": revision, "patchset": "fixture",
                  "depot_tools_revision": "d" * 40, "runner": "synthetic-runner",
                  "architecture": "x86_64", "xcode_version": "16.4",
                  "macos_sdk_version": "15.5", "macos_deployment_target": "13.0",
                  "ninja_targets": ["libEGL", "libGLESv2"],
                  "gn_args": {"is_debug": False, "is_component_build": False, "target_cpu": "x64",
                              "use_system_xcode": True, "clang_use_chrome_plugins": False,
                              "mac_deployment_target": "13.0", "mac_min_system_version": "13.0",
                              "angle_assert_always_on": False, "angle_enable_metal": True,
                              "angle_enable_gl": False, "angle_enable_vulkan": False,
                              "angle_enable_swiftshader": False, "angle_enable_null": False,
                              "angle_enable_wgpu": False, "angle_enable_cl": False,
                              "angle_build_tests": False, "build_angle_deqp_tests": False,
                              "symbol_level": 0}}
        candidate_patch = copy.deepcopy(patch)
        candidate_patch.update(id="candidate", candidate_for_new_angle=True,
                               angle_revision=candidate_revision)
        candidate_recipe = copy.deepcopy(recipe)
        candidate_recipe.update(id="candidate", candidate_default=True,
                                chrome_source="2.3.400.5", angle_revision=candidate_revision,
                                patchset="candidate")
        docs = {
            "chrome/1.2.300.4.json": {"schema_version": 1, "kind": "chrome_source", "chrome_version": "1.2.300.4", "chromium_revision": "c" * 40, "angle_revision": revision},
            "chrome/2.3.400.5.json": {"schema_version": 1, "kind": "chrome_source", "chrome_version": "2.3.400.5", "chromium_revision": "d" * 40, "angle_revision": candidate_revision, "candidate_only": True},
            f"angle-revisions/{revision}.json": {"schema_version": 1, "kind": "angle_source", "revision": revision},
            f"angle-revisions/{candidate_revision}.json": {"schema_version": 1, "kind": "angle_source", "revision": candidate_revision},
            "patchsets/fixture.json": patch,
            "patchsets/candidate.json": candidate_patch,
            "recipes/fixture.json": recipe,
            "recipes/candidate.json": candidate_recipe,
        }
        docs["chrome/1.2.300.4.json"]["baseline_inputs"] = {
            "patchset_id": "fixture", "patch_sha256": patch["patch_sha256"],
            "recipe_id": "fixture", "recipe_sha256": validator.recipe_sha256(recipe),
        }
        for rel, value in docs.items():
            (catalog / rel).write_text(json.dumps(value), encoding="utf-8")
        return temp, catalog, docs

    def test_real_catalog(self):
        validator.validate_catalog(ROOT / "catalog")
        baseline = json.loads((ROOT / "catalog/chrome/156.0.8078.48.json").read_text(encoding="utf-8"))
        candidate = json.loads((ROOT / "catalog/chrome/158.0.8127.37.json").read_text(encoding="utf-8"))
        baseline_patch = json.loads((ROOT / "catalog/patchsets/metal-family1-v1.json").read_text(encoding="utf-8"))
        candidate_patch = json.loads((ROOT / "catalog/patchsets/metal-family1-158-v1.json").read_text(encoding="utf-8"))
        baseline_recipe = json.loads((ROOT / "catalog/recipes/macos-x64-metal-v1.json").read_text(encoding="utf-8"))
        candidate_recipe = json.loads((ROOT / "catalog/recipes/macos-x64-metal-158-v1.json").read_text(encoding="utf-8"))
        self.assertNotIn("candidate_only", baseline)
        self.assertTrue(candidate["candidate_only"])
        self.assertEqual(baseline["baseline_inputs"]["patchset_id"], "metal-family1-v1")
        self.assertFalse(baseline_patch["candidate_for_new_angle"])
        self.assertTrue(candidate_patch["candidate_for_new_angle"])
        self.assertFalse(baseline_recipe["candidate_default"])
        self.assertTrue(candidate_recipe["candidate_default"])

    def test_synthetic_catalog_accepts_complete_mapping(self):
        temp, catalog, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        validator.validate_catalog(catalog)

    def test_synthetic_catalog_accepts_multiple_complete_mappings(self):
        temp, catalog, docs = self.fixture()
        self.addCleanup(temp.cleanup)
        second = copy.deepcopy(docs["chrome/1.2.300.4.json"])
        second["chrome_version"] = "3.4.500.6"
        second["chromium_revision"] = "e" * 40
        (catalog / "chrome/3.4.500.6.json").write_text(json.dumps(second), encoding="utf-8")
        second_recipe = copy.deepcopy(docs["recipes/fixture.json"])
        second_recipe["id"] = "fixture-two"
        second_recipe["chrome_source"] = "3.4.500.6"
        second_recipe["candidate_default"] = False
        (catalog / "recipes/fixture-two.json").write_text(json.dumps(second_recipe), encoding="utf-8")
        second["baseline_inputs"] = {
            "patchset_id": "fixture", "patch_sha256": docs["patchsets/fixture.json"]["patch_sha256"],
            "recipe_id": "fixture-two", "recipe_sha256": validator.recipe_sha256(second_recipe),
        }
        (catalog / "chrome/3.4.500.6.json").write_text(json.dumps(second), encoding="utf-8")
        validator.validate_catalog(catalog)

    def test_candidate_source_cannot_carry_a_fixed_baseline(self):
        temp, catalog, _ = self.fixture()
        self.addCleanup(temp.cleanup)
        candidate_path = catalog / "chrome/2.3.400.5.json"
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
        candidate["baseline_inputs"] = {}
        candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
        with self.assertRaisesRegex(validator.CatalogError, "candidate-only"):
            validator.validate_catalog(catalog)

    def test_negative_cases(self):
        mutations = [
            ("malformed Chrome version", "chrome/1.2.300.4.json", lambda d: d.update(chrome_version="1.2.3")),
            ("malformed source pin", "chrome/1.2.300.4.json", lambda d: d.update(chromium_revision="not-a-pin")),
            ("missing mapping", "chrome/1.2.300.4.json", lambda d: d.update(angle_revision="e" * 40)),
            ("duplicate mapping", "chrome/duplicate.json", lambda d: d.update(chrome_version="1.2.300.4")),
            ("missing fixed baseline inputs", "chrome/1.2.300.4.json", lambda d: d.pop("baseline_inputs")),
            ("missing bound patchset", "chrome/1.2.300.4.json", lambda d: d["baseline_inputs"].update(patchset_id="missing")),
            ("conflicting bound patch hash", "chrome/1.2.300.4.json", lambda d: d["baseline_inputs"].update(patch_sha256="0" * 64)),
            ("missing bound recipe", "chrome/1.2.300.4.json", lambda d: d["baseline_inputs"].update(recipe_id="missing")),
            ("conflicting bound recipe hash", "chrome/1.2.300.4.json", lambda d: d["baseline_inputs"].update(recipe_sha256="0" * 64)),
            ("bad patch hash", "patchsets/fixture.json", lambda d: d.update(patch_sha256="0" * 64)),
            ("unsupported recipe ref", "recipes/fixture.json", lambda d: d.update(patchset="missing")),
            ("invalid GN type", "recipes/fixture.json", lambda d: d["gn_args"].update(angle_enable_metal="true")),
            ("patch order mismatch", "patchsets/fixture.json", lambda d: (d.update(apply_order=["src/other.cc"]), d.update(source_blobs={"src/other.cc": "b" * 40}))),
        ]
        for label, rel, mutate in mutations:
            with self.subTest(label=label):
                temp, catalog, docs = self.fixture()
                self.addCleanup(temp.cleanup)
                target = catalog / rel
                if rel in docs:
                    data = json.loads(target.read_text(encoding="utf-8"))
                elif rel == "chrome/duplicate.json":
                    data = copy.deepcopy(docs["chrome/1.2.300.4.json"])
                mutate(data)
                target.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(validator.CatalogError):
                    validator.validate_catalog(catalog)


if __name__ == "__main__":
    unittest.main()
