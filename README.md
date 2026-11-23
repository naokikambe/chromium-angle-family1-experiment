# Chrome Stable ANGLE Family 1 maintenance

This repository prepares exact-version, unsigned `libEGL.dylib` and `libGLESv2.dylib` candidates for Chrome Stable on macOS x86_64. It keeps the Chrome → Chromium commit → ANGLE commit mapping, the reviewed Family 1 patch, the fixed Chrome 156 recipe, candidate defaults for unregistered versions, and the artifact checks together.

Repository changes are reviewed on a dedicated local branch based on a verified GitHub `main` tip. Publication, pull request changes, and integration into `main` each require their own approval. See [the main publication plan](docs/main-publication-plan.md).

## Current pinned baseline

- Chrome Stable: `156.0.8078.48`
- Chromium commit: `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c`
- ANGLE commit from Chromium `DEPS`: `3b89d84e9d59f75675ac4e2bef58fc068a9f0577`
- Patchset: `metal-family1-v1`
- Family 1 patch SHA-256: `dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0`
- Recipe: `macos-x64-metal-v1` (build-recipe SHA-256 `bea88d9ec894cb1ab875755be52c93b85ed9029d2f00a9f31363123e4d43d7ba`)
- Recipe target: x86_64, `macos-15-intel`, Xcode 16.4, SDK 15.5, deployment target 13.0

The 156 source, patchset, and recipe binding is versioned under [`catalog/`](catalog/README.md). The resolver uses that exact binding for the known version; changing the new-version candidate defaults does not change the 156 reproduction. A separately selected alternate recipe is recorded as an explicit trial. Unregistered versions continue to use the unique designated candidate patchset and default recipe. PR validation checks the proposed merge with `main`, then builds the exact 156 and 158 sources through the same build and verification script as the monitor and baseline reproduction. A configured build is not evidence of a successful run; inspect both matrix results before integration. The scheduled monitor remains guarded to `main`.

Chrome 158.0.8127.37 is recorded as a candidate-only source mapping with its own patchset and recipe; it is not a fixed baseline. Its addition left the Chrome 156 reproduction pins and patch bytes unchanged.

## Workflows

- [Stable monitor and candidate build](.github/workflows/watch-chrome-stable.yml) checks fully rolled out Mac Stable releases, resolves exact source inputs, and builds validated candidates.
- [Pull request validation](.github/workflows/validate-pr.yml) runs synthetic checks followed by full 156/158 ANGLE builds for same-repository PRs, with read-only repository permissions and seven-day validation artifacts.
- [Baseline reproduction](.github/workflows/reproduce-baseline.yml) manually reproduces the exact Chrome 156 source, patchset, and recipe binding. It is not a general arbitrary-version build entrypoint.

## Automation and local tools

The scheduled workflow checks Google’s Mac Stable VersionHistory API, requires a fully served release, and compares exact four-part versions with the last formally successful build. Detection history is retained separately and never counts as success. It fetches the exact Chromium version tag, checks `chrome/VERSION` and `DEPS`, then resolves the known baseline binding or the designated new-version defaults before applying a patch and running focused synthetic Family 1 policy tests. Passing candidates are built and uploaded with a license and source/toolchain/hash manifest, including the input-selection mode. Unknown ANGLE revisions can reach build only if the patch applies and the tests pass. Failed candidates remain indexed for attention. A matching failed input fingerprint blocks automatic rebuilds; a changed relevant input allows one new scheduled attempt. CI success is a build candidate only, not device compatibility or adoption.

The local helper is manually invoked and reads only the selected Chrome app and this repository’s indexed artifacts. It does not watch Chrome updates or request a build. Start with `python3 scripts/local-angle.py --help`; examples and operation order are in [local installation](docs/local-installation.md).

```sh
python3 scripts/validate-catalog.py
python3 -m unittest discover -s tests
```

The PR check also runs privacy and safe-push fixture checks. These commands validate catalog and synthetic behavior. They do not build ANGLE or establish real Chrome, Metal, KOOV, Bluetooth, USB, or device acceptance.

## Documents

- [Architecture and boundaries](docs/architecture.md)
- [Stable update policy](docs/update-policy.md)
- [Build and artifact format](docs/build-and-artifacts.md)
- [Patch maintenance and provenance](docs/patch-maintenance.md)
- [Local installation tools](docs/local-installation.md)
- [Acceptance checklist](docs/acceptance-checklist.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Probe provenance and media/WebGL check](docs/probes.md)
- [Automation operations](docs/automation-operations.md)
- [Chrome 158 candidate and retry plan](docs/158-candidate-retry-plan.md)
- [Chrome 156 baseline](docs/156-baseline.md)
- [Project history and migration scope](docs/history.md)
- [Publication privacy](docs/publication-privacy.md)
- [Safe-push procedure](docs/safe-push-and-gc-procedure.md)

## License

Repository-authored workflow files, scripts (including the retained probe scripts under `src/probes/`), and documentation are licensed under the BSD 3-Clause License; see [LICENSE](LICENSE). This scoped grant does not make a blanket statement about the origin or license of every file in the current tree.

ANGLE, Chromium, and other third-party components and generated artifacts remain subject to their respective licenses. The workflow collects applicable ANGLE and third-party notices in its build artifact.

Google Chrome and KOOV binaries, teaching materials, and assets are outside this repository's license. This is an independent project, is not affiliated with or endorsed by Google, the Chromium project, the ANGLE project, or KOOV, and provides no warranty or safety guarantee.
