# Phase 3 — Dynamic ANGLE experiment

Status: Chrome `154.0.8037.58` runtime artifact CI and Phase 3D VM observation
are complete. The separately approved `.58` real-device attempt reached GPU
initialization and stopped there; its evidence and remaining boundaries are in
[`docs/phase5-real-device-observation.md`](phase5-real-device-observation.md).
Any new device preflight still requires separate approval. The release-manifest
migration history and procedure below remain part of this record.
The CI workflows described here do not modify the installed Chrome app, sign
code, launch Chrome or KOOV, or access existing browser profiles. The separately
approved device procedure and its current `.58` observation are recorded below.

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

`ensure-angle-release-artifact.sh` is Step 0. It reads the installed source
Chrome version without modifying the app and searches only direct child artifact
directories of an explicitly supplied cache root. Exactly one artifact is
reused only when its `angle-release-v1` manifest, sidecar, and both dylib hashes
verify and its Chrome version matches. With no match, Step 0 dispatches the
pinned build workflow for that version, waits for the newly created run,
downloads it into a new cache child, verifies it, and prints the selected path.
Multiple matches fail closed. Step 0 is read-only toward source Chrome and the
repository, but build dispatch and artifact download are explicit side effects.

At preflight, the source app's `CFBundleShortVersionString` is checked again and
must exactly equal the selected release manifest's `CHROME_VERSION`. A mismatch
is fatal. No script embeds a Chrome version, ANGLE revision, run ID, artifact
name, or dylib hash.

The operational sequence is Step 0 artifact assurance, Step 1 Phase 3C
preflight through signing dry-run, Step 2 separately approved real signing, and
Step 3 separately approved Case B/Case C launch and evidence collection.

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
`--dry-run`. New attempts require an explicitly supplied, currently valid
Apple Development identity SHA-1 and replace Google's Developer ID signature
and notarization on the test copy. They are not normal browsing or distribution
copies. The signing path does not preserve the Google identity-bound
`application-identifier`, `keychain-access-groups`, associated-domains, or
browser public-key-credential entitlements. It supplies Chromium's base device
permissions (including Bluetooth, USB, camera, microphone, print, location,
and Photos) to the app and the Chromium JIT entitlement only to the GPU and
renderer helper app bundles. Those JIT-capable helpers use Chromium's
`runtime,kill,restrict` flags rather than inheriting Library Validation; the
outer app retains its Library Validation flag. Signature, entitlements, CodeDirectory,
strict-verification, and GPU process load evidence are retained before any
later runtime decision. Strict verification failures are not ignored or retried
automatically.

Preparation records the artifact and pre-sign Libraries bytes. Apple Development
signing legitimately changes the bytes of every signed Mach-O in Libraries,
including the two added ANGLE dylibs. Therefore signing writes a separate,
external post-sign Libraries inventory and checksum, referenced by signing
receipt schema `phase3-angle-signing-receipt-v3`. Run and collection require
that signed inventory, while continuing to enforce the prepared entry set,
types, and symlink targets. Receipt v1 is not accepted; legacy v2 receipts are
accepted only for immutable historical ad-hoc attempts and are never emitted by
the current signing path.

The complete synthetic fixture suites are accepted only through the pinned
Phase 3B and Phase 3C GitHub Actions workflows on `macos-15-intel`. Local full
fixture execution is prohibited. CI success is required before requesting a new
human-approved real-device preflight. CI success alone does not establish that
the GPU process loads both external dylibs or that KOOV works.

### GPU-startup diagnostic mode

`run-dynamic-angle-test.sh` accepts the explicit optional
`--diagnostic-gpu-startup` flag for a separately approved diagnostic Case B or
Case C attempt. It adds Chrome VLOG selection for `gl_display` and
`gl_initializer_mac`, requests a 15-second Chrome GPU startup trace in JSON
format, and writes it to the case results directory. The selected mode, trace
path, and requested format are recorded in `run-metadata.txt`; the normal case
does not enable it.

Chromium's tracing switch documentation describes proto as the default format:
it can be written incrementally and retain more data if the browser terminates
unexpectedly. JSON is easier to read, but it can be incomplete or truncated if
the browser exits before trace finalization. Therefore `json` in the command
line or metadata records a requested format only. The result file must be
checked after the run before calling it valid JSON or using its contents.

This mode does not alter the signed test-copy bytes or add a dyld entitlement.
In particular, it deliberately does not rely on `DYLD_*` environment variables:
the Hardened Runtime may ignore those variables without the
`allow-dyld-environment-variables` entitlement. The trace and `stderr.log` can
show EGL/GPU initialization failures, but do not prove external ANGLE loading.
`stderr.log` and other process evidence remain independent of trace format. A
trace, its requested flags, or its existence do not prove external ANGLE
loading or an internal ANGLE stage. Direct evidence naming both test-copy
dylib absolute paths under the same GPU PID remains the required load proof;
the two paths may be evidenced across `lsof` and `vmmap` records for that PID.

The real-device launcher also starts a bounded live observer before Chrome is
launched. It records GPU-process command lines and best-effort `lsof`/`vmmap`
evidence while the process is alive, restricted to the test-copy Framework and
isolated profile. The collector waits briefly for the observer's completion
marker; browser exit is normal completion, while a launch timeout, observer
deadline, or missing completion marker is recorded as incomplete. Live
observation is evidence preservation only; it does not change the launch,
signing, or fallback decision.

## Phase 3 results and transition to Family 1 work

The release-manifest workflow was exercised with Chrome `154.0.8037.58`.
The selected artifact recorded matching Chrome, Chromium, and ANGLE revisions,
and its manifest, sidecar, and two dylib hashes passed verification. Phase 3B
and Phase 3C synthetic fixture workflows passed, including release-manifest,
current-only Framework, attempt-root, signing, and diagnostic-mode assertions.

The historical Phase 3D VM observation recorded GPU-correlated dyld evidence
for each external ANGLE library, while the stock control did not. The probe at
that time aggregated the two library signals independently, so it did not
prove that both paths appeared under the same GPU PID. Treat the historical
`both-replacement-libraries-gpu-loaded` label as unverified same-process
evidence until the raw artifact is re-reviewed or a corrected probe reruns.
Even confirmed same-PID loading would not prove successful Metal initialization
on the target Mac.

As a historical pre-`.58` Intel Mac attempt, a test copy was prepared and
Apple Development signed with strict verification passing. The Keychain prompt
was declined intentionally. Chrome launched, and repeated GPU processes
recorded `Initialization of all (1) EGL display types failed`, followed by
`GLDisplayEGL::Initialize failed` and GPU-process exit. The same EGL failure was
also recorded during that historical comparison with the unmodified installed
Chrome using the same ANGLE/Metal startup switches. This record predates the
current `.58` attempt; it does not establish current `.58` stock behavior,
current `.58` dynamic ANGLE loading, or the root cause of the current failure.

On the Intel Mac, the `.58` test copy was prepared and Apple Development
signed with strict verification passing. Chrome launched with a fresh disposable
profile. In live repeat Case B and Case C observations, the GPU process selected
Intel HD Graphics 5000 / Metal, then failed with
`Initialization of all (1) EGL display types failed`, followed by
`GLDisplayEGL::Initialize failed`, GPU-process exit, and
`--use-gl=disabled` fallback. Case C added only
`--disable-angle-features=requireGpuFamily2`; the switch reached the GPU
process, but this does not prove that the feature override was recognized or
that initialization should succeed.

The real-device observation did not establish external dylib loading. Neither
`lsof`/`vmmap` nor the collector named both replacement dylibs, and the short-lived
GPU process disappeared before collection in some observations. This is an
unresolved load observation, not evidence that dynamic ANGLE was absent. WebGL
and KOOV were not started after the GPU initialization stop condition. The
details and sanitized attempt record are in
[`docs/phase5-real-device-observation.md`](phase5-real-device-observation.md).

The next work is read-only analysis of the existing GPU startup trace, stderr
extract, GPU process arguments, and failure ordering. If needed, disposable
diagnostic tooling should improve direct load and feature-override proof. Then
the fixed revision's Family 1 gate and runtime patch should be diagnosed at
source level, with CI and VM validation before any separately approved repeat
device test. The current runtime patch adds a nil command-queue guard; it does
not bypass the Family 1 availability gate.

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
