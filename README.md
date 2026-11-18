# Chrome Stable ANGLE Family 1 maintenance

This repository prepares exact-version, unsigned `libEGL.dylib` and `libGLESv2.dylib` candidates for Chrome Stable on macOS x86_64. It keeps the Chrome → Chromium commit → ANGLE commit mapping, the reviewed Family 1 patch, the fixed Chrome 156 recipe, candidate defaults for unregistered versions, and the artifact checks together.

The maintenance candidate is based on the existing `main` base and is reviewed on the dedicated `migration/angle-maintenance` branch. Integration is through a Draft PR and a separately approved squash merge; this repository does not use direct commits or pushes to `main`. The migration does not import the old experiment branch history. The publication guard and privacy checks remain in place; see [the main publication plan](docs/main-publication-plan.md).

## Current pinned baseline

- Chrome Stable: `156.0.8078.48`
- Chromium commit: `d0c02bfad08ec92a6ffcf989e53cd995e6381a4c`
- ANGLE commit from Chromium `DEPS`: `3b89d84e9d59f75675ac4e2bef58fc068a9f0577`
- Patchset: `metal-family1-v1`
- Family 1 patch SHA-256: `dedac2c57daa69b72fe78bbde443f45d5a6cdfe128d4022049a35c0dbbf501b0`
- Recipe: `macos-x64-metal-v1` (build-recipe SHA-256 `bea88d9ec894cb1ab875755be52c93b85ed9029d2f00a9f31363123e4d43d7ba`)
- Recipe target: x86_64, `macos-15-intel`, Xcode 16.4, SDK 15.5, deployment target 13.0

The 156 source, patchset, and recipe binding is versioned under [`catalog/`](catalog/README.md). The resolver uses that exact binding for the known version; changing the new-version candidate defaults does not change the 156 reproduction. A separately selected alternate recipe is recorded as an explicit trial. Unregistered versions continue to use the unique designated candidate patchset and default recipe. The baseline reproduction workflow is manual and fixed to the catalog binding; it has not been run as part of this migration. The PR validation runs synthetic and static checks only. The scheduled monitor is guarded to `main` and activates only after a separately approved integration to the default branch.

## Workflows

- [Stable monitor and candidate build](.github/workflows/watch-chrome-stable.yml) checks fully rolled out Mac Stable releases, resolves exact source inputs, and builds validated candidates.
- [Pull request validation](.github/workflows/validate-pr.yml) runs catalog, synthetic, privacy, and safe-push fixture checks with read-only permissions.
- [Baseline reproduction](.github/workflows/reproduce-baseline.yml) manually reproduces the exact Chrome 156 source, patchset, and recipe binding. It is not a general arbitrary-version build entrypoint.

## Automation and local tools

The scheduled workflow checks Google’s Mac Stable VersionHistory API, requires a fully served release, fetches the exact Chromium version tag, checks `chrome/VERSION` and `DEPS`, then resolves the known baseline binding or the designated new-version defaults before applying a patch and running focused synthetic Family 1 policy tests. Passing candidates are built and uploaded with a license and source/toolchain/hash manifest, including the input-selection mode. Unknown ANGLE revisions can reach build only if the patch applies and the tests pass. Failures are indexed as needing attention; the patch is never rewritten automatically.

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
- [Automation operations](docs/automation-operations.md)
- [Chrome 156 baseline](docs/156-baseline.md)
- [Project history and migration scope](docs/history.md)
- [Publication privacy](docs/publication-privacy.md)
- [Safe-push procedure](docs/safe-push-and-gc-procedure.md)

The repository has no project-wide license file. The ANGLE license is retained for the upstream source covered by the patch and build artifact; it does not license this repository as a whole.
