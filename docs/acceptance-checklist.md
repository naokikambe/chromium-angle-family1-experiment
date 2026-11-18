# Acceptance checklist

CI acceptance and device acceptance are separate.

## CI candidate

- [ ] Official Mac Stable release data confirms explicit 100% rollout.
- [ ] Exact Chromium tag version, commit, and `DEPS` ANGLE pin agree.
- [ ] Catalog source mapping agrees where known; new revisions are identified as candidates.
- [ ] Patch hash, path order, application, and baseline source blobs (when applicable) pass.
- [ ] All three focused synthetic policy tests pass against the patched ANGLE sources.
- [ ] Xcode, SDK, architecture, GN recipe, depot_tools, and deployment target match pins.
- [ ] Only `libEGL` and `libGLESv2` were built; both pass Mach-O, architecture, minimum OS, unsigned, and test-symbol checks.
- [ ] Manifest, license/notice list, library hashes, run ID, artifact ID, and expiry agree.
- [ ] Final-state and pre-build checkpoint archives use the `stable-monitor-state.json` member; interrupted checkpoints are never indexed as success or automatically rebuilt.
- [ ] CI status is recorded as candidate generation only, with compatibility and adoption left `not-assessed`.

## Owner-controlled app and runtime

- [ ] The selected app’s exact four-part version and explicitly selected runtime architecture match an unexpired successful artifact and an available executable slice.
- [ ] The selected Chrome Framework `Versions/<exact version>/Libraries` path and `Versions/Current` target agree.
- [ ] The new copy’s content matches the source before library replacement; the original app and profile remain untouched.
- [ ] The in-app installation binding preserves the exact CI manifest hash and unsigned library hashes.
- [ ] After signing, a local in-app and external receipt binds CI hashes to signed library hashes and CDHashes; strict signature and tamper checks pass.
- [ ] The Finder registration and daily KOOV apps have their own Bluetooth purpose string, selected Chrome path, architecture, profile binding, and correct URL/app-ID entrypoint.
- [ ] The copied Chrome app also has the reviewed Bluetooth purpose string. No unrelated permission strings were added.
- [ ] Owner-selected signing succeeds and strict signature verification passes.
- [ ] The launcher reuses only its bound dedicated profile and only the reviewed ANGLE switches.
- [ ] Synthetic video/WebGL checks pass before real product testing.
- [ ] Owner separately observes runtime library loading, Metal, expected WebGL draw/readback, and video behavior.
- [ ] If applicable, owner tests Bluetooth/USB, save/reload, normal shutdown/restart, and a sustained session.
- [ ] Owner decides whether to adopt or retain the candidate. A CI pass is not that decision.

No device test, Chrome launch, signing operation, profile change, or Bluetooth/USB operation was performed in this migration.
