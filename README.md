# Chromium ANGLE Family 1 Experiment

Reproducible, standalone ANGLE build configuration for a macOS x86_64 experiment.

Pinned Chrome/Chromium/ANGLE revisions, artifact digests, CI run IDs, phase
status, and remaining device boundaries are maintained in the phase documents
below rather than duplicated in this overview:

- `docs/phase-status.md` — current phase status and primary CI records
- `docs/phase3d-vm-observability.md` — VM artifact, dynamic/stock, GPU/EGL,
  and WebGL observation records
- `docs/phase5-metal-family1-vm-stub-plan.md` — Phase 5 admission conditions,
  runtime artifact design, and real-device transition boundary
- `docs/phase3-dynamic-angle.md` — separately approved device-test procedure

The base workflow builds ANGLE targets `libEGL` and `libGLESv2` on
`macos-15-intel`. The explicit Phase 5 runtime workflow is separate and
opt-in; its artifact and VM observations are recorded in the phase documents.
VM observation may use verified libraries inside a disposable Chrome for
Testing bundle on the runner. It does not modify `/Applications`, the source
Chrome app, an existing user profile, retained evidence, or KOOV.

Real-device test-copy creation, xattr changes, signing, Chrome launch, profile
use, and KOOV operation remain separately approved human actions. The original
Chrome app and retained retry/evidence directories are read-only to the
automated workflows.

## License

Repository-authored workflow files, scripts, and documentation are licensed
under the BSD 3-Clause License; see `LICENSE`. ANGLE, Chromium, and other
third-party components and generated artifacts remain subject to their
respective licenses. The workflow collects applicable ANGLE and third-party
notices in its build artifact.

Google Chrome and KOOV binaries, teaching materials, and assets are outside
this repository's license. This is an independent experimental project, is not
affiliated with or endorsed by Google, Sony, the Chromium project, the ANGLE
project, KOOV, or the OCLP project, and provides no warranty or safety
guarantee.
