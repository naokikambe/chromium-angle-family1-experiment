import hashlib
import json
import os
from pathlib import Path
import plistlib
import subprocess
import stat
import tempfile
import unittest
from unittest.mock import patch

from src.maintenance_angle.artifact import ArtifactError, LIBRARIES, sha256
from src.maintenance_angle.launcher import LauncherError, load_usage_template, with_usage_descriptions
from src.maintenance_angle.local import (LocalError, _copy_tree_without_flags, create_finder_launchers,
                             _tree_fingerprint, create_launcher, find_loader_library_dir, plan_install, prepare_copy,
                             sign_copy, verify_launcher_script, verify_prepared_app)
from tests.test_artifact_handling import make_artifact

ROOT = Path(__file__).resolve().parents[1]
VERSION = "156.0.8078.48"
KOOV_ID = "a" * 32
OTHER_FRAMEWORK_VERSION = ".".join(("157", "0", "1", "2"))
NONMATCHING_FRAMEWORK_VERSION = ".".join(("155", "0", "1", "2"))


def make_chrome(root: Path, name: str = "Chrome Candidate.app", version: str = VERSION) -> Path:
    app = root / name
    executable = app / "Contents/MacOS/Chrome"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    info = {"CFBundleExecutable": "Chrome", "CFBundleShortVersionString": version,
            "CFBundleIdentifier": "org.example.Chrome"}
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    library_dir = app / "Contents/Frameworks/Chrome Framework.framework/Versions" / version / "Libraries"
    library_dir.mkdir(parents=True)
    (library_dir.parent.parent / "Current").symlink_to(version)
    return app


def write_binding(app: Path, *, architecture: str = "x86_64", build_key: str = "e" * 64,
                  installation_id: str = "install-123", hashes: dict | None = None,
                  manifest_hash: str = "f" * 64) -> dict:
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    version = info["CFBundleShortVersionString"]
    library = find_loader_library_dir(app, version)
    binding = {"schema": "angle-local-binding-v1", "installation_id": installation_id,
               "artifact_manifest_sha256": manifest_hash, "artifact_build_key": build_key,
               "chrome_version": version, "runtime_architecture": architecture,
               "framework_libraries_relative": library.relative_to(app).as_posix(),
               "ci_unsigned_library_hashes": hashes or {name: "0" * 64 for name in LIBRARIES}}
    resources = app / "Contents/Resources"
    resources.mkdir(exist_ok=True)
    (resources / "ANGLE_LOCAL_BINDING.json").write_text(json.dumps(binding, sort_keys=True), encoding="utf-8")
    return binding


class LauncherTests(unittest.TestCase):
    def test_reviewed_template_supplies_bluetooth_and_only_bluetooth(self):
        template = load_usage_template(ROOT / "templates/launcher/usage-descriptions.json")
        result = with_usage_descriptions({"CFBundleIdentifier": "synthetic.app"}, template, {"bluetooth"})
        self.assertIn("NSBluetoothAlwaysUsageDescription", result)
        self.assertEqual(set(result) - {"CFBundleIdentifier"}, {"NSBluetoothAlwaysUsageDescription"})

    def test_missing_bluetooth_template_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "template.json"
            path.write_text(json.dumps({"schema": "angle-launcher-usage-v1", "required_features": {}}))
            with self.assertRaises(LauncherError):
                load_usage_template(path)

    def test_launcher_script_has_explicit_architecture_profile_and_koov_entrypoint(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            write_binding(app)
            from src.maintenance_angle.launcher import ARCH_COMMAND, launcher_script
            daily = launcher_script(app, root / "profile", app / "Contents/MacOS/Chrome",
                                    "x86_64", koov_app_id=KOOV_ID)
            registration = launcher_script(app, root / "profile", app / "Contents/MacOS/Chrome",
                                           "x86_64", registration_url="https://koov.example/register")
            self.assertIn(f'exec {ARCH_COMMAND} "-$EXPECTED_ARCHITECTURE"', daily)
            self.assertIn("--disable-angle-features=requireGpuFamily2", daily)
            self.assertIn("ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1", daily)
            self.assertIn("--app-id=" + KOOV_ID, daily)
            self.assertIn("--app=https://koov.example/register", registration)
            self.assertNotIn("--enable-features", daily)

    def test_launcher_reuses_same_profile_and_rejects_binding_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            binding = write_binding(app)
            profile = root / "dedicated-profile"
            command = root / "launch-koov.command"
            fake_bin = root / "bin"
            fake_bin.mkdir()
            arch = fake_bin / "arch"
            arch.write_text("#!/bin/bash\n[[ \"$1\" == -x86_64 ]] || exit 91\nshift\nexec \"$@\"\n")
            arch.chmod(0o755)
            from src.maintenance_angle import launcher as launcher_module
            with patch.object(launcher_module, "ARCH_COMMAND", str(arch)):
                create_launcher(app, profile, command, ROOT / "templates/launcher/usage-descriptions.json",
                                koov_app_id=KOOV_ID)
            self.assertEqual(verify_launcher_script(command, app, profile)["status"], "VALID")
            marker_path = profile / ".angle-profile-binding.json"
            marker = json.loads(marker_path.read_text())
            self.assertEqual(marker["installation_id"], binding["installation_id"])
            self.assertEqual(marker["chrome_app_path"], str(app.resolve()))
            self.assertEqual(marker["runtime_architecture"], "x86_64")
            self.assertEqual(marker["profile_path"], str(profile.resolve()))
            chrome = app / "Contents/MacOS/Chrome"
            chrome.write_text("#!/bin/bash\nprintf '%s\\n' \"$*\" >> \"$CHROME_INVOCATION_LOG\"\n"
                              "for arg in \"$@\"; do case \"$arg\" in --user-data-dir=*) "
                              "mkdir -p \"${arg#*=}/Default\";; esac; done\n")
            chrome.chmod(0o755)
            log = root / "invocations.log"
            env = os.environ.copy()
            env["PATH"] = str(fake_bin) + ":" + env.get("PATH", "/usr/bin:/bin")
            env["CHROME_INVOCATION_LOG"] = str(log)
            for _ in range(2):
                result = subprocess.run(["/bin/bash", str(command)], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(len(log.read_text().splitlines()), 2)
            self.assertTrue((profile / "Default").is_dir())

            marker["chrome_app_path"] = str(root / "Different Chrome.app")
            marker_path.write_text(json.dumps(marker))
            result = subprocess.run(["/bin/bash", str(command)], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("bound to a different installation", result.stderr)
            self.assertEqual(len(log.read_text().splitlines()), 2)

    def test_finder_apps_separate_registration_and_daily_app_id_with_own_bluetooth_usage(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            write_binding(app)
            result = create_finder_launchers(
                app, root / "profile", root / "Finder Launchers",
                ROOT / "templates/launcher/usage-descriptions.json", koov_app_id=KOOV_ID,
                registration_url="https://koov.example/register", bundle_id_prefix="org.example.angle")
            self.assertEqual(result["status"], "FINDER_LAUNCHERS_READY_BEFORE_SIGNING")
            registration = root / "Finder Launchers/KOOV Registration.app"
            daily = root / "Finder Launchers/KOOV ANGLE Family1.app"
            for bundle in (registration, daily):
                info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
                self.assertEqual(info["CFBundlePackageType"], "APPL")
                self.assertTrue(info["NSBluetoothAlwaysUsageDescription"])
                self.assertTrue((bundle / "Contents/MacOS/Launcher").stat().st_mode & 0o100)
            registration_script = (registration / "Contents/MacOS/Launcher").read_text()
            daily_script = (daily / "Contents/MacOS/Launcher").read_text()
            self.assertIn("--app=https://koov.example/register", registration_script)
            self.assertIn("--app-id=" + KOOV_ID, daily_script)
            self.assertIn(str(app.resolve()), daily_script)
            self.assertIn("--user-data-dir=\"$PROFILE_PATH\"", daily_script)
            self.assertIn("ANGLE_PHASE5_ENABLE_METAL_FAMILY1=1", daily_script)
            self.assertTrue(plistlib.loads((app / "Contents/Info.plist").read_bytes())[
                "NSBluetoothAlwaysUsageDescription"])

    def test_koov_values_are_validated_before_any_launcher_is_created(self):
        from src.maintenance_angle.launcher import validate_koov_app_id
        with self.assertRaises(LauncherError):
            validate_koov_app_id("private-or-invalid")

    def test_copy_preserves_contents_and_internal_symlink_without_copying_xattrs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Source.app"
            (source / "Contents/Versions/A").mkdir(parents=True)
            (source / "Contents/Versions/A/file").write_text("synthetic")
            (source / "Contents/Versions/Current").symlink_to("A")
            destination = root / "Copy.app"
            _copy_tree_without_flags(source, destination)
            self.assertEqual((destination / "Contents/Versions/A/file").read_text(), "synthetic")
            self.assertTrue((destination / "Contents/Versions/Current").is_symlink())
            with self.assertRaises(LocalError):
                _copy_tree_without_flags(source, destination)

    def test_readonly_source_copy_stays_writable_through_embedding_and_binding(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            library_dir = app / "Contents/Frameworks/Chrome Framework.framework/Versions" / VERSION / "Libraries"
            (library_dir / "libEGL.dylib").write_bytes(b"old egl")
            (library_dir / "libGLESv2.dylib").write_bytes(b"old gles")
            readonly_file = app / "Contents/readonly-resource.dat"
            readonly_file.write_bytes(b"synthetic read-only input")
            artifact = root / "artifact"
            manifest = make_artifact(artifact)

            source_modes = {}
            for directory, dirs, files in os.walk(app, topdown=True, followlinks=False):
                base = Path(directory)
                source_modes[base] = 0o555
                for name in dirs:
                    child = base / name
                    if not child.is_symlink():
                        source_modes[child] = 0o555
                for name in files:
                    child = base / name
                    if not child.is_symlink():
                        source_modes[child] = 0o555 if child == app / "Contents/MacOS/Chrome" else 0o444
            for path, mode in source_modes.items():
                path.chmod(mode)

            selected = {"app_path": str(app.resolve()), "version": VERSION,
                        "architectures": ["x86_64"], "runtime_architecture": "x86_64",
                        "bundle_identifier": "org.example.Chrome",
                        "executable": str(app / "Contents/MacOS/Chrome")}
            target = root / "Chrome Readonly Copy.app"
            try:
                source_before = _tree_fingerprint(app)
                with patch("src.maintenance_angle.local.inspect_app", return_value=selected):
                    plan = prepare_copy(app, artifact, target, root / "profile", "x86_64")

                self.assertEqual(plan["status"], "PREPARED_UNSIGNED")
                self.assertEqual(plan["library_hashes"], manifest["libraries"])
                self.assertEqual(_tree_fingerprint(app), source_before)
                self.assertEqual(stat.S_IMODE((app / "Contents").stat().st_mode), 0o555)
                self.assertEqual(stat.S_IMODE((app / "Contents/Info.plist").stat().st_mode), 0o444)
                self.assertEqual(stat.S_IMODE((app / "Contents/MacOS/Chrome").stat().st_mode), 0o555)
                self.assertTrue((target / "Contents/Frameworks/Chrome Framework.framework/Versions/Current").is_symlink())
                self.assertEqual((target / "Contents/readonly-resource.dat").read_bytes(),
                                 b"synthetic read-only input")
                self.assertTrue(stat.S_IMODE((target / "Contents/MacOS/Chrome").stat().st_mode) & 0o111)
                self.assertTrue(stat.S_IMODE((target / "Contents/readonly-resource.dat").stat().st_mode) & 0o200)
                self.assertTrue(stat.S_IMODE((target / "Contents/Frameworks/Chrome Framework.framework/Versions" /
                                              VERSION / "Libraries").stat().st_mode) & 0o200)
                binding = json.loads((target / "Contents/Resources/ANGLE_LOCAL_BINDING.json").read_text())
                self.assertEqual(binding["ci_unsigned_library_hashes"], manifest["libraries"])
                copied_libraries = target / "Contents/Frameworks/Chrome Framework.framework/Versions" / VERSION / "Libraries"
                for name in LIBRARIES:
                    self.assertEqual(sha256(copied_libraries / name), manifest["libraries"][name])
            finally:
                for path, mode in source_modes.items():
                    path.chmod(mode | 0o700 if path.is_dir() else mode | 0o200)

    def test_failed_readonly_copy_removes_only_its_partial_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Readonly Source.app"
            (source / "Contents").mkdir(parents=True)
            (source / "Contents/first.dat").write_bytes(b"synthetic")
            outside = root / "outside.dat"
            outside.write_bytes(b"untouched")
            (source / "Contents/escape").symlink_to("../../outside.dat")
            (source / "Contents/first.dat").chmod(0o444)
            (source / "Contents").chmod(0o555)
            source.chmod(0o555)
            destination = root / "new-copy.app"
            try:
                with self.assertRaisesRegex(LocalError, "escapes"):
                    _copy_tree_without_flags(source, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(outside.read_bytes(), b"untouched")
                self.assertEqual((source / "Contents/first.dat").read_bytes(), b"synthetic")
            finally:
                (source / "Contents").chmod(0o755)
                source.chmod(0o755)

    def test_versioned_framework_selects_exact_app_version_and_validates_current(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            framework = app / "Contents/Frameworks/Chrome Framework.framework/Versions"
            other = framework / f"{OTHER_FRAMEWORK_VERSION}/Libraries"
            other.mkdir(parents=True)
            selected = framework / VERSION / "Libraries"
            self.assertEqual(find_loader_library_dir(app, VERSION), selected)
            (framework / "Current").unlink()
            (framework / "Current").symlink_to(OTHER_FRAMEWORK_VERSION)
            with self.assertRaisesRegex(LocalError, "Current does not select Chrome version"):
                find_loader_library_dir(app, VERSION)
            (framework / "Current").unlink()
            (framework / "Current").symlink_to(VERSION)
            with self.assertRaisesRegex(LocalError, "no unique Framework version"):
                find_loader_library_dir(app, NONMATCHING_FRAMEWORK_VERSION)

    def test_universal_chrome_requires_explicit_available_architecture_and_matching_artifact(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            artifact_dir = root / "artifact"
            manifest = make_artifact(artifact_dir)
            selected = {"app_path": str(app.resolve()), "version": VERSION,
                        "architectures": ["arm64", "x86_64"], "runtime_architecture": None,
                        "bundle_identifier": "org.example.Chrome",
                        "executable": str(app / "Contents/MacOS/Chrome")}
            with patch("src.maintenance_angle.local.inspect_app", return_value=selected) as inspect:
                plan = plan_install(app, artifact_dir, root / "copy.app", root / "profile", "x86_64")
            self.assertEqual(plan["architecture"], "x86_64")
            self.assertEqual(plan["library_directory_relative"],
                             f"Contents/Frameworks/Chrome Framework.framework/Versions/{VERSION}/Libraries")
            inspect.assert_called_once_with(app, "x86_64")
            with patch("src.maintenance_angle.local.inspect_app", return_value=selected):
                with self.assertRaises(ArtifactError):
                    plan_install(app, artifact_dir, root / "copy-arm.app", root / "profile-arm", "arm64")
            self.assertEqual(manifest["architecture"], "x86_64")

    def test_inspection_reports_universal_slices_and_rejects_unavailable_runtime_arch(self):
        with tempfile.TemporaryDirectory() as temp:
            app = make_chrome(Path(temp))
            completed = subprocess.CompletedProcess([], 0, stdout="x86_64 arm64\n", stderr="")
            with patch("src.maintenance_angle.local.subprocess.run", return_value=completed):
                from src.maintenance_angle.local import inspect_app
                result = inspect_app(app, "arm64")
                self.assertEqual(result["architectures"], ["x86_64", "arm64"])
                self.assertEqual(result["runtime_architecture"], "arm64")
                with self.assertRaisesRegex(LocalError, "not present"):
                    inspect_app(app, "x86_64h")

    def test_prepare_copy_binds_original_ci_hashes_and_versioned_runtime_architecture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            artifact = root / "artifact"
            manifest = make_artifact(artifact)
            selected = {"app_path": str(app.resolve()), "version": VERSION, "architectures": ["x86_64"],
                        "runtime_architecture": "x86_64", "bundle_identifier": "org.example.Chrome",
                        "executable": str(app / "Contents/MacOS/Chrome")}
            target = root / "Chrome Copy.app"
            with patch("src.maintenance_angle.local.inspect_app", return_value=selected):
                plan = prepare_copy(app, artifact, target, root / "profile", "x86_64")
            self.assertEqual(plan["status"], "PREPARED_UNSIGNED")
            self.assertEqual(plan["library_hashes"], manifest["libraries"])
            self.assertEqual(plan["architecture"], "x86_64")
            binding = json.loads((target / "Contents/Resources/ANGLE_LOCAL_BINDING.json").read_text())
            self.assertEqual(binding["ci_unsigned_library_hashes"], manifest["libraries"])
            self.assertEqual(binding["chrome_version"], VERSION)
            self.assertEqual(binding["runtime_architecture"], "x86_64")
            self.assertTrue(plan["installation_id"])

    def test_mock_signing_receipt_separates_ci_and_signed_hashes_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = make_chrome(root)
            artifact_dir = root / "artifact"
            manifest = make_artifact(artifact_dir)
            library_dir = find_loader_library_dir(app, VERSION)
            for name in LIBRARIES:
                shutil_path = artifact_dir / name
                (library_dir / name).write_bytes(shutil_path.read_bytes())
            info_path = app / "Contents/Info.plist"
            info = plistlib.loads(info_path.read_bytes())
            info["NSBluetoothAlwaysUsageDescription"] = "Synthetic usage description"
            info_path.write_bytes(plistlib.dumps(info))
            binding = write_binding(app, hashes=manifest["libraries"], build_key=manifest["build_key"],
                                    manifest_hash=sha256(artifact_dir / "ANGLE_ARTIFACT_MANIFEST.json"))
            receipt = root / "private-local" / "angle-receipt.json"
            selected = {"app_path": str(app.resolve()), "version": VERSION, "architectures": ["x86_64"],
                        "runtime_architecture": "x86_64", "bundle_identifier": "org.example.Chrome",
                        "executable": str(app / "Contents/MacOS/Chrome")}

            def fake_codesign(command, **kwargs):
                if "--sign" in command:
                    target = Path(command[-1])
                    if target.name in LIBRARIES:
                        target.write_bytes(target.read_bytes() + b"\nsynthetic-codesign-payload")
                    return subprocess.CompletedProcess(command, 0, "", "")
                if "--display" in command:
                    target = Path(command[-1])
                    cdhash = hashlib.sha256(str(target).encode()).hexdigest()[:40]
                    metadata = (f"CDHash={cdhash}\nAuthority=Unit Test Identity\n"
                                "TeamIdentifier=UNITTEST\nSignature=adhoc\n")
                    return subprocess.CompletedProcess(command, 0, "", metadata)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("src.maintenance_angle.local.inspect_app", return_value=selected), \
                    patch("src.maintenance_angle.local.subprocess.run", side_effect=fake_codesign):
                sign_copy(app, artifact_dir, "UNIT TEST IDENTITY", receipt, execute=True)
                verified = verify_prepared_app(app, artifact_dir, require_signature=True, receipt_path=receipt)
                self.assertEqual(verified["signature"], "strict-verified-with-local-receipt")
                self.assertEqual(verified["ci_unsigned_library_hashes"], manifest["libraries"])
                self.assertNotEqual(verified["installed_library_hashes"], manifest["libraries"])
                external = json.loads(receipt.read_text())
                self.assertEqual(external["ci_unsigned_library_hashes"], manifest["libraries"])
                self.assertEqual(external["signed_library_hashes"], verified["installed_library_hashes"])
                self.assertEqual(binding["installation_id"], external["installation_id"])

                external["artifact_build_key"] = "f" * 64
                receipt.write_text(json.dumps(external))
                with self.assertRaisesRegex(LocalError, "receipts do not match"):
                    verify_prepared_app(app, artifact_dir, require_signature=True, receipt_path=receipt)
                external["artifact_build_key"] = manifest["build_key"]
                receipt.write_text(json.dumps(external))

                tampered_lib = library_dir / "libEGL.dylib"
                tampered_lib.write_bytes(tampered_lib.read_bytes() + b"tamper")
                with self.assertRaisesRegex(LocalError, "signed receipt"):
                    verify_prepared_app(app, artifact_dir, require_signature=True, receipt_path=receipt)


if __name__ == "__main__":
    unittest.main()
