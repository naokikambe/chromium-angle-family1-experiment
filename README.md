# Chromium ANGLE Family 1 Experiment

Reproducible, standalone ANGLE build configuration for a macOS x86_64 experiment.

- Chrome: `154.0.8037.17`
- Chromium: `62d2fcb41a84e4dcefd8c4da7dfa534e6c482854`
- ANGLE: `8efd15f71c27cd0bc2a9cf0074d77e899ca9c448`
- Current stage: Phase 2B — build and artifact validation only

The workflow builds unmodified ANGLE targets `libEGL` and `libGLESv2` on
`macos-15-intel`. It does not modify Chrome, place libraries into a browser,
launch Chrome or KOOV, or perform any MacBookAir6,1 testing.

See `docs/phase-status.md` for current status and `docs/phase2-build.md` for
the build and validation design.

## License

Repository-authored workflow files, scripts, and documentation are licensed
under the BSD 3-Clause License; see `LICENSE`. ANGLE, Chromium, and other
third-party components and generated artifacts remain subject to their
respective licenses. The workflow collects applicable ANGLE and third-party
notices in its build artifact.

Google Chrome and KOOV binaries, teaching materials, and assets are outside
this repository's license. This is an independent experimental project, is not
affiliated with or endorsed by Google, the Chromium project, the ANGLE project,
or KOOV, and provides no warranty or safety guarantee.
