# Phase 3 — Dynamic ANGLE experiment

Status: release-manifest migration is under implementation and requires successful
Phase 3B and Phase 3C synthetic CI before any new device preflight is authorized.
This workflow does not modify the installed Chrome app, sign code, launch Chrome or
KOOV, or access existing browser profiles.

## Release selection and provenance

New ANGLE builds are selected through the build workflow's required
`chrome_version` input. The accepted value is a four-component numeric version.
The workflow resolves the exact Chromium tag to a commit, verifies the tag's
`chrome/VERSION`, and extracts `angle_revision` from that commit's `DEPS`. Build
inputs remain pinned where required: depot_tools revision, Actions revisions,
runner, GN configuration, and timeouts.

Every new artifact contains `ANGLE_RELEASE_MANIFEST` and its SHA-256 sidecar.
Schema `angle-release-v1` records Chrome version, Chromium and ANGLE revisions,
depot_tools revision, both dylib hashes, artifact schema/name, run ID, UTC build
time, and GN-args hash. Artifact validation checks the sidecar, schema, manifest
fields, GN args when present, and each dylib's bytes. No old manifest is treated
as this schema. The Phase 3 test-copy manifest records the exact release-manifest
SHA-256 used to prepare it.

At preflight, the source app's `CFBundleShortVersionString` must exactly equal
the release manifest's `CHROME_VERSION`. A mismatch is fatal; updating Chrome
does not silently select or substitute an artifact. Download and prepare scripts
accept an explicitly selected artifact directory/run rather than embedding a
Chrome version, ANGLE revision, run ID, artifact name, or dylib hashes in code.

## Attempt directories and immutable history

Each preflight uses a new, explicitly named `attempt-YYYYMMDD-HHMMSS` root.
The output app and results directory must be its direct children. The root must
be absolute, unused, non-symlinked, user-owned, outside the source app, artifact,
and `/Applications` trees, and have a safe existing parent. Existing retry0–12
directories and their evidence remain immutable historical records; they are not
inputs to the new attempt workflow.

## Framework version policy

The active concrete Framework version is discovered from the source bundle's
`Versions/Current` link and checked against the release Chrome version. Only that
active version is retained in the isolated test copy; the installed source bundle
is never changed. Removed-version inventories, the active version, Libraries
baseline/post-install inventories, and release-manifest digest are recorded in
the external test-copy evidence. Existing `Libraries` baseline entries must be
preserved; the only new entries are the two ANGLE dylibs with hashes from the
release manifest. Unknown, missing, replaced, or colliding entries fail closed.

The Libraries symlink is accepted only when its literal target is
`Versions/Current/Libraries` and its canonical resolution remains within the
test-copy Framework. Symlink, bundle, inventory, signature-receipt, and
Case B/Case C isolation checks remain part of the synthetic fixtures.

## Signing and runtime boundary

Copy validation precedes ANGLE placement. Signing is an explicitly confirmed,
test-copy-only operation; the preflight command calls signing only with
`--dry-run`. Ad-hoc signing replaces Google's Developer ID signature and
notarization on that test copy. It is not a normal browsing or distribution
copy. Signature, entitlements, CodeDirectory, strict-verification, and GPU
process load evidence are retained before any later runtime decision. Strict
verification failures are not ignored or retried automatically.

The complete synthetic fixture suites are accepted only through the pinned
Phase 3B and Phase 3C GitHub Actions workflows on `macos-15-intel`. Local full
fixture execution is prohibited. CI success is required before requesting a new
human-approved real-device preflight. CI success alone does not establish that
the GPU process loads both external dylibs or that KOOV works.

## Legacy artifacts

The artifact built for Chrome `154.0.8037.45` (run `35515036255`, Chromium
revision `731082f0a26ce4b3976c3d82943092f5d13daf13`, ANGLE revision
`72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`) is retained as a legacy record.
Its fixed hashes and artifact identity are historical facts, not current script
constants. It does not contain the new `angle-release-v1` manifest and must not
be silently accepted by the new download, prepare, sign, run, collect, or
preflight path. Do not use it for a different Chrome version.

The original dynamic ANGLE rationale remains: Chromium forwards the dynamic ANGLE
switch to the GPU process and resolves `libGLESv2.dylib` and `libEGL.dylib` from
the Framework `Libraries` directory. This establishes the intended loading path,
not successful runtime loading on a specific device. Case A/B/C comparisons and
direct GPU-process evidence are required; Family 1-specific ANGLE changes remain
outside this phase.
