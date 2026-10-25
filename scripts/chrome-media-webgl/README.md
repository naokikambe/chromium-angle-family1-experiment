# Chrome for Testing media and WebGL probe

This runner checks H.264 MP4 and VP8 WebM playback, WebGL1 draw/readback, and
ANGLE/Metal library mapping in Chrome for Testing `154.0.8037.0`. It accepts an
already prepared app bundle and two caller-supplied synthetic media inputs. It
checks their SHA-256 values, uses a fresh temporary profile and a loopback-only
page, and writes a summary without local paths, usernames, PIDs, command lines,
device strings, or raw diagnostics.
The implementation uses Python's standard library and this project's
`scripts/page-recovery/probe.py` CDP helper.

## Rights-cleared inputs

Provide an H.264 MP4 fixture and a VP8 WebM fixture that you are authorized to
use for this test. Confirm their authorship and redistribution terms before
sharing the files or their source. The runner does not establish provenance or
license compliance; `--confirm-rights-cleared-synthetic-inputs` records the
operator's declaration. It rejects empty inputs, inputs over 32 MiB, and files
whose supplied SHA-256 does not match. Codec patent and other distribution
conditions must be reviewed separately from copyright.

Calculate each input's SHA-256 in the environment where you run the test. Set
`CFT_APP_PATH`, `H264_FIXTURE`, `H264_SHA256`, `VP8_FIXTURE`, `VP8_SHA256`, and
`PROBE_OUTPUT` to the selected inputs and a new output directory, then run:

```sh
python3 scripts/chrome-media-webgl/run_probe.py \
  --app "$CFT_APP_PATH" \
  --mode family1 \
  --h264-fixture "$H264_FIXTURE" \
  --h264-sha256 "$H264_SHA256" \
  --vp8-fixture "$VP8_FIXTURE" \
  --vp8-sha256 "$VP8_SHA256" \
  --confirm-rights-cleared-synthetic-inputs \
  --out-dir "$PROBE_OUTPUT"
```

Use `--mode default` for Chrome's default ANGLE configuration. The `family1`
mode uses the reviewed Family 1 ANGLE options and opt-in from
`scripts/page-recovery/persistent_cookie_runner.py`. The supplied app must be
Chrome for Testing `154.0.8037.0` with a valid strict deep signature. The
runner does not download, assemble, modify, or sign Chrome or ANGLE, and does
not visit KOOV or access credentials.

The output summary records fixture hashes and sizes, playback progress, the
WebGL1 pixel result, and whether the expected ANGLE EGL/GLES names and Metal
framework mapped in the same GPU process. Runtime mapping does not prove the
source revision or hashes of the loaded ANGLE libraries. A successful probe
does not establish KOOV playback, installation, lifecycle, or device
integration acceptance.

The reported experiment used specific synthetic media inputs. Reproducing its
measurements from public materials requires redistribution-cleared fixtures or
a rights-cleared generation procedure, plus a public CfT artifact URL and
SHA-256 and the CfT + ANGLE assembly and signing procedure.
