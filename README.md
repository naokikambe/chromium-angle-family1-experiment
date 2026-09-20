# Chromium ANGLE Family 1 Experiment

Reproducible, standalone ANGLE build configuration for a macOS x86_64 experiment.

- Chrome: `154.0.8037.45`
- Chromium: `731082f0a26ce4b3976c3d82943092f5d13daf13`
- ANGLE: `72b8f72a7587ec776d7d2a57d275a6e9b1781b1d`
- Current stage: Phase 3B preparation — no device test has run

The workflow builds unmodified ANGLE targets `libEGL` and `libGLESv2` on
`macos-15-intel`. It does not modify Chrome, place libraries into a browser,
launch Chrome or KOOV, or perform any MacBookAir6,1 testing.

See `docs/phase-status.md` for current status and `docs/phase2-build.md` for
the build and validation design. `docs/phase3-dynamic-angle.md` defines the
separate, opt-in device-test procedure; it does not authorize a Chrome launch.

Phase 3B uses only a user-owned test copy. Its explicit signing command clears
that copy's attributes and replaces Google's Developer ID/notarized signature
with an ad-hoc signature; it must never be used for normal browsing or an
existing Chrome profile. The original Chrome app is read-only to these tools.

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
