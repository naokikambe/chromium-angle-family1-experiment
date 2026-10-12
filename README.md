# Chromium ANGLE Family 1 Experiment

macOS x86_64 ANGLE experiments and a concrete plan to recover HTTP page
display in an Apple Development-signed Chromium copy.

Current work: Phase 5 page recovery. Historical device experiments reached
Metal/EGL initialization and minimal WebGL1 drawing, but signed stock and
ANGLE-added Chromium copies failed HTTP document navigation. The device agent
has identified the cause for current S0 under the GPU-disabled diagnostic
condition; normal-Keychain stock recovery remains pending. The recovery kit provides portable checks. Device runtime
findings and unresolved acceptance checks belong in the local investigation
report.

The current device investigation is complete only when the root cause of the
page-display failure is established by runtime evidence and controlled
failure/success comparisons. Retaining re-signing as the explanation requires
new causal evidence beyond the previous observations, including an explanation
of failures after first signing. ANGLE integration and full KOOV validation are
subsequent work.

- [Revised execution plan and findings](docs/phase5-page-recovery-replan.md)
- [Public sources supporting the Keychain plan](docs/phase5-keychain-public-evidence.md)
- [Initial execution plan](docs/phase5-page-recovery-plan.md)
- [Copyable handoff for the physical Mac](docs/phase5-page-recovery-handoff.md)
- [Continue the Keychain investigation](docs/phase5-keychain-investigation-handoff.md)
- [Ordinary-Keychain stock recovery handoff](docs/phase5-normal-keychain-handoff.md)
- [Complete device handoff: stock, custom ANGLE, and KOOV](docs/phase5-device-completion-handoff.md)
- [Experiment history](docs/phase5-page-recovery-history.md)
- [Recovery kit and commands](scripts/page-recovery/README.md)

For the next stage, obtain the `phase5-page-recovery` branch from GitHub on the
target MacBookAir6,1. The handoff includes clone/fetch instructions, GUI-user and
Keychain checks, and the order of the device experiments. Browser bundles and
previous evidence are inputs on the Mac; they are not included in this repository.

The branch includes the device-side symlink fix from `cc49dd9`, post-observation
capture from `383310b`, and configurable startup wait from `71d5bb1`. The device
agent reports cause identification complete for current S0 with GPU disabled:
an unanswered Safe Storage authorization blocks progress; after denial and a
Keychain error, a subsequently started fixture request and rendering succeed.
Individual callback transitions remain source-derived. The complete device
handoff first tests successful ordinary-Keychain access, normal GPU rendering,
and encrypted test-data reuse after restart, then proceeds to a DEPS-matched
Family 1 ANGLE build, assembly and first signing, and KOOV acceptance. Each stage
has a prerequisite and completion gate. Denial and mock success are diagnostic
results; new owner permissions are not inferred from prior one-time responses.

From the repository root, verify the portable kit with:

```sh
python3 -m unittest discover -s scripts/page-recovery -p 'test_kit.py' -v
```

The signing trial creates a fresh copy of the wholly unsigned Intel Chromium
snapshot `1689422`. It prepares an inspectable component signing plan before
executing first signing. The scripts do not establish that signing settings
caused the historical failure; the plan compares actual device evidence first.

The original standalone ANGLE build baseline remains:

- Chrome: `154.0.8037.17`
- Chromium: `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`
- ANGLE: `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`
- Baseline stage: Phase 2B — build and artifact validation

The baseline workflow builds unmodified ANGLE targets `libEGL` and `libGLESv2` on
`macos-15-intel`. It does not modify Chrome, place libraries into a browser,
launch Chrome or KOOV, or perform any MacBookAir6,1 testing.

See `docs/phase-status.md` for current status and `docs/phase2-build.md` for
the build and validation design. The repository itself has no selected license;
the workflow separately collects applicable ANGLE and third-party notices in
its build artifact. The pinned Chromium entitlement references included with
the recovery kit retain their upstream provenance and license.
