# Phase 3 macOS signing references

Use the pinned Chromium revision recorded by `ANGLE_RELEASE_MANIFEST` when a
source file must be consulted. The links below are the public sources for the
development-signing policy used by Phase 3.

* [Chromium macOS signing README](https://chromium.googlesource.com/chromium/src/+/main/chrome/installer/mac/signing/README.md)
  describes the `--identity` and `--development` flow. It also states that a
  Google-branded app locally signed with non-Google credentials must not retain
  entitlements tied to Google's signing identity.
* [Chromium signing parts](https://chromium.googlesource.com/chromium/src/+/main/chrome/installer/mac/signing/parts.py)
  is the reference for inside-out signing order and the renderer/GPU helper
  entitlement roles.
* [Chromium base app entitlements](https://chromium.googlesource.com/chromium/src/+/main/chrome/app/app-entitlements.plist)
  is the source of the retained device and privacy permissions.
* [Google branded entitlements](https://chromium.googlesource.com/chromium/src/+/main/chrome/app/app-entitlements-chrome.plist)
  identifies the application identifier, keychain groups, associated domains,
  and browser credential entitlements that must not be reused with a personal
  Apple Development identity.
* [Apple Worldwide Developer Relations certificates](https://www.apple.com/certificateauthority/)
  lists the current intermediate certificates. A development certificate that
  appears in Keychain Access but is absent from `security find-identity` may be
  missing its required WWDR intermediate.

## Failure routing

1. If `security find-identity -v -p codesigning` does not list the chosen
   identity, stop before preflight/signing and repair its local certificate,
   private key, or trust chain.
2. If strict verification fails, preserve the new attempt unchanged and inspect
   its saved signing results; do not retry in place.
3. If strict verification passes but launch is rejected by taskgated, preserve
   the attempt and collect read-only signature, entitlement, Gatekeeper, and
   taskgated diagnostics before changing signing policy.
4. Gatekeeper/notarization assessment and taskgated launch validation are
   distinct checks. Neither is evidence that the GPU loaded external ANGLE.
