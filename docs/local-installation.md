# Local installation tools

The owner starts the local helper. It reads the selected Chrome app and this repository’s indexed artifact. It never checks Chrome’s latest release, starts an automatic build, launches Chrome, logs in, or connects a device.

```sh
python3 scripts/local-angle.py inspect --app "/Applications/Chrome for Testing.app"
python3 scripts/local-angle.py inspect --app "/Applications/Chrome for Testing.app" \
  --runtime-architecture x86_64
python3 scripts/local-angle.py match --repository OWNER/REPOSITORY \
  --version 156.0.8078.48 --architecture x86_64
python3 scripts/local-angle.py fetch --repository OWNER/REPOSITORY \
  --version 156.0.8078.48 --architecture x86_64 --destination "/path/to/new-artifact"
python3 scripts/local-angle.py plan --app "/Applications/Chrome for Testing.app" \
  --artifact-dir "/path/to/new-artifact" --target-copy "/path/to/Chrome Family1.app" \
  --profile-dir "/path/to/profile-family1" --runtime-architecture x86_64
```

`GH_TOKEN` may contain the owner’s existing read-only token with `actions:read`. Exact four-part version, macOS platform, selected runtime architecture, successful status, non-expired artifact metadata, run/artifact ID, build key, manifest, library hashes, and license files must agree. `fetch` extracts to a new unused directory and removes a partial extraction if checks fail.

Chrome can contain a universal executable. `inspect` reports its available slices; `plan` and `prepare` require an explicit runtime architecture. The selected slice must exist in the Chrome executable and match the artifact architecture. The catalog currently produces x86_64 artifacts, so an arm64 request stops unless an exact arm64 artifact is later published. The helper chooses `Chrome Framework.framework/Versions/<exact Chrome version>/Libraries` only when `Versions/Current` resolves to that same numeric version. It refuses mismatches and ambiguous layouts.

After reviewing the plan, `prepare` copies the selected app to a new path without copying file flags or extended attributes, compares copied content, executable bits, and symlink targets, places the verified libraries in the exact Framework version directory, and writes a local installation binding. Copied directories remain owner-writable, and copied files retain their execute bits while gaining owner-write access through library embedding, Info.plist/binding updates, and signing. A failed operation removes only the new copy created by that operation; it does not change the selected original app. Immutable freeze happens only after signed verification and receipt checks.

The official Finder entry is two generated `.app` bundles. Replace the clearly synthetic registration URL and 32-character app-ID sample below with the owner-confirmed KOOV registration URL and Chrome web-app ID, and choose a local bundle-ID prefix:

```sh
python3 scripts/local-angle.py prepare --app "/Applications/Chrome for Testing.app" \
  --artifact-dir "/path/to/new-artifact" --target-copy "/path/to/Chrome Family1.app" \
  --profile-dir "/path/to/profile-family1" --runtime-architecture x86_64
python3 scripts/local-angle.py finder-launchers --app-copy "/path/to/Chrome Family1.app" \
  --profile-dir "/path/to/profile-family1" --output-dir "/path/to/KOOV Launchers" \
  --koov-registration-url "https://koov.example/owner-provided-registration-url" \
  --koov-app-id "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  --bundle-id-prefix "org.example.angle"
```

`KOOV Registration.app` opens the supplied URL in the selected Chrome copy for first-time setup; account registration and login remain owner actions. `KOOV ANGLE Family1.app` uses Chrome’s `--app-id=<ID>` mode for daily launch. Both scripts use the absolute selected Chrome path, explicit runtime architecture, dedicated profile, and reviewed ANGLE switches. Each Finder app’s own `Info.plist` contains `NSBluetoothAlwaysUsageDescription`; the copied Chrome app also receives the reviewed Bluetooth purpose string. The generator prepares and inspects the bundles but does not compile AppleScript, sign or launch them, change TCC permissions, or interact with a controller. The owner must separately review local signing and test the Finder/TCC behavior.

The generator creates the dedicated profile directory with a binding marker containing the installation ID, exact Chrome app path/version, runtime architecture, and artifact build key. Daily launches reuse that same profile only while the marker and copied-app binding match. The launcher rejects another app, another version or architecture, a changed installation binding, or an unbound existing profile.

An optional `.command` daily helper can be generated after the Finder apps:

```sh
python3 scripts/local-angle.py launcher --app-copy "/path/to/Chrome Family1.app" \
  --profile-dir "/path/to/profile-family1" --output "/path/to/launch-family1.command" \
  --koov-app-id "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

Generate launchers before signing because the Bluetooth purpose strings are part of the bundle Info plists. Signing first verifies that the current unsigned libraries match the exact CI artifact, then signs the libraries and Framework. It records the CI unsigned hashes separately from post-sign hashes and CDHashes. A signed receipt is stored inside the signed app and mirrored to a required absolute local path outside the app bundle and repository:

```sh
python3 scripts/local-angle.py sign --app-copy "/path/to/Chrome Family1.app" \
  --artifact-dir "/path/to/new-artifact" --receipt "/path/to/private-local/angle-receipt.json" \
  --identity "OWNER_SELECTED_IDENTITY"
```

`sign` prints the signing plan by default. The owner may add `--execute` after reviewing it; the private key is not uploaded. Signed verification checks the exact CI manifest/binding, post-sign library hashes, CDHashes, both copies of the receipt, and strict code signatures:

```sh
python3 scripts/local-angle.py verify --app-copy "/path/to/Chrome Family1.app" \
  --artifact-dir "/path/to/new-artifact" --require-signature \
  --receipt "/path/to/private-local/angle-receipt.json"
python3 scripts/local-angle.py freeze --app-copy "/path/to/Chrome Family1.app" \
  --artifact-dir "/path/to/new-artifact" --receipt "/path/to/private-local/angle-receipt.json" --execute
```

`freeze --execute` requires signed verification and a valid receipt before applying the immutable flag. `freeze --unfreeze` reverses the flag. These are local owner operations; CI does not run them. Login, OS prompts, runtime observation, real hardware, adoption, and deletion decisions remain with the owner.

Keep app bundles, profiles, downloaded artifacts, generated launcher apps, signatures, receipts, and test results outside the repository. Never commit them.
