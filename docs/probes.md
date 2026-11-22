# Probe provenance and media/WebGL check

## Probe source and license provenance

The three retained probe modules came from project-authored scripts, not from Chromium implementation source. Their paths were moved into `src/probes/` by the maintenance migration recorded in commit `37bd6d9d3dd122b2373a8573f5c4646c88f43d4a`. The current probe paths do not have commit ancestry back to the former file revisions, so those commits are source references rather than ancestors of the current files.

| Current file | Former source and relevant fixed commits | Migration change |
| --- | --- | --- |
| [`probe.py`](../src/probes/probe.py) | `scripts/page-recovery/probe.py`; source history includes `fa2f3f7606a86856ca56749ad1eba2dd7cca92ca`, `383310b82b639535051069eca2180a70cd0d7cf3`, `71d5bb1658080e3fc2f5af308c3442f3c2737296`, and `e2f2ce5e934f7255ebc0a314968b382d01d73748` | Moved into the importable `src.probes` package with approximately 99% content similarity. Its CDP import now uses the package-relative module. |
| [`cdp_transport.py`](../src/probes/cdp_transport.py) | `scripts/page-recovery/cdp_transport.py`; relevant source history includes `fa2f3f7606a86856ca56749ad1eba2dd7cca92ca` and `c58a15b208c6f7ab4afc8af099d337b4efe5f868`. The former handoff also references the project-authored [`phase5-unsigned-cdp-probe.py` at `292c7e2`](https://github.com/naokikambe/chromium-angle-family1-experiment/blob/292c7e2bab8bd06e9cf2ec50d7d20a451393290d/scripts/phase5-unsigned-cdp-probe.py). | Exact content match to the former helper (`R100`); retained as a shared project helper. |
| [`media_webgl.py`](../src/probes/media_webgl.py) | `scripts/chrome-media-webgl/run_probe.py`, present in the former source tree at `e2f2ce5e934f7255ebc0a314968b382d01d73748` | Moved with approximately 92% content similarity. The current package import and required exact browser version/architecture arguments are authoritative; the former Chrome 154 command is obsolete. |

The root [project license](../LICENSE) preserves the existing BSD 3-Clause scope for repository-authored workflow files, scripts, and documentation. `src/probes/` contains the moved scripts described above. This statement does not classify every file in the current tree or license third-party source.

The retained [`reference/LICENSE`](../scripts/page-recovery/reference/LICENSE) is byte-identical to Chromium's `LICENSE` at revision [`82303c21a18acdc256c6264cd2ed0e1588df99d4`](https://chromium.googlesource.com/chromium/src/+/82303c21a18acdc256c6264cd2ed0e1588df99d4/LICENSE), SHA-256 `368cca1106be99d39ecd32a38d8305585d802a475effb66380b91ffc9bcf709b`. The former provenance record associated that Chromium license with copied entitlement plists. Those plists and the signing kit are not present in the current tree and are not needed by these probes. The retained license text is preserved as third-party provenance; it does not make the project-authored probe modules Chromium code.

The prior source and license records can be verified against Git history. No old entitlement files, signature adapters, private experiment output, or media fixtures are required to use the current media/WebGL probe.

## Current media/WebGL CLI

Run from the repository root on macOS. Both forms are supported:

```sh
python3 src/probes/media_webgl.py --help
python3 -m src.probes.media_webgl --help
```

The real probe requires an existing Chrome for Testing `.app` bundle whose `CFBundleShortVersionString` exactly matches the supplied full version. Its executable must contain the requested architecture, and `codesign --verify --deep --strict` must pass before launch. Supported architectures are `x86_64` and `arm64`. The probe runs the selected architecture explicitly.

Provide two nonempty, synthetic, rights-cleared inputs: an H.264 video in an MP4 file and a VP8 video in a WebM file. Each must be at most 32 MiB. Compute and supply the exact SHA-256 for each file. The probe verifies those hashes and requires `--confirm-rights-cleared-synthetic-inputs`; that flag records the operator's declaration and does not verify authorship or redistribution rights. Confirm permission to use the fixtures and review codec/patent distribution conditions separately. Keep fixture files outside the repository.

Example using a new local output directory:

```sh
python3 -m src.probes.media_webgl --app "$CFT_APP" --expected-version "$CFT_VERSION" --expected-architecture "$CFT_ARCHITECTURE" --mode family1 --h264-fixture "$H264_MP4" --h264-sha256 "$H264_SHA256" --vp8-fixture "$VP8_WEBM" --vp8-sha256 "$VP8_SHA256" --confirm-rights-cleared-synthetic-inputs --out-dir "$NEW_OUTPUT_DIRECTORY"
```

Every option shown is required. `--mode` is either `default` or `family1`. The `family1` mode sets the opt-in environment value and ANGLE/Metal browser switches defined by the current implementation. The probe creates a fresh temporary Chrome profile, serves the fixtures on loopback, and removes that profile after the run. It refuses an output directory that already exists. The owner runs the command locally and chooses where to retain the summary; do not add results or test videos to the repository.

The command prints a JSON summary and, after creating the output directory, writes `summary.json` there. Argument, platform, or output-directory failures can return a JSON error on stdout before a summary file is written. Check `pass`, `failure_stage`, `probe_completed`, `browser_version`, `expected_browser_architecture`, `signature_valid_before_launch`, `media_inputs`, both `media` results, `webgl1`, `same_gpu_process_mapping`, and `browser_exited_cleanly`. The probe itself sends the play-button input through CDP using `Input.dispatchMouseEvent`; the operator does not need to click manually. Each `media.h264` and `media.vp8` result reports `play_click_observed`, `play_promise_resolved`, `progressed`, `error_free`, `decoded_frames`, `dropped_frames`, and `pass`. A media pass requires those first four checks, at least one decoded frame, and playback readiness with the video unpaused in both snapshots. `dropped_frames` is reported but is not itself a pass condition. The readiness and paused values are not copied into the JSON summary, so `pass` remains the authoritative result if the exported fields appear to pass.

`webgl1` reports `shader_compile`, `program_link`, `draw`, `readback`, `pixel`, `expected_pixel`, and `pass`; success requires both shader compilations, a linked program, a draw, a successful readback, the expected pixel, and no GL error. `same_gpu_process_mapping` reports `browser_process_matched`, `angle_egl`, `angle_gles`, `metal`, and `same_gpu_process`. `family1` requires `same_gpu_process=true`; `default` reports the mapping without using it as a pass condition. The mapping check does not verify library source revision or hashes.

If `failure_stage` is present, inspect that stage and its relevant inputs or operation. Early CLI failures are `arguments`, `unsupported-platform`, and `output-directory`. The probe stages are `browser-input`, `signature-verification`, `fixture-integrity`, `profile-and-loopback-page`, `browser-startup`, `synthetic-page`, `play-button-input`, `media-and-webgl-sampling`, `same-gpu-process-library-mapping`, and `browser-cleanup`. Check the app version and architecture, signature, fixture hashes and rights, then the corresponding result fields. If `pass=false` and `failure_stage=null`, treat this as a measured result failure when `probe_completed=true`: inspect `media.h264`, `media.vp8`, `webgl1`, and, in `family1` mode, `same_gpu_process_mapping`. Measurement can complete with failing result fields and a null stage. The probe emits a summary rather than browser logs.

A passing run is a bounded synthetic check of that exact app and input set. It does not establish KOOV playback or acceptance, real-device GPU support, Bluetooth/USB behavior, signed product adoption, or correctness with other versions and fixtures. Any real browser run and its results remain local owner operations.
