#!/usr/bin/env python3
"""Focused synthetic checks for the non-acceptance WebGL diagnostic runner."""
from pathlib import Path
import copy
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import webgl1_diagnostic_runner as runner


class WebGL1DiagnosticRunnerTests(unittest.TestCase):
    def test_launch_configuration_reuses_exact_family1_arguments_and_opt_in(self):
        launch = runner.family1_launch_configuration(Path("/synthetic/Chromium"),
                                                    Path("/synthetic/fresh-profile"))
        self.assertEqual(launch["argv"][-5:-1], list(runner.FAMILY1_ARGUMENTS))
        self.assertEqual(launch["runtime_environment"], {runner.OPT_IN_ENV: "1"})
        self.assertNotIn("--use-mock-keychain", launch["argv"])

    def test_existing_profile_can_be_reused_without_creating_or_changing_entries(self):
        with tempfile.TemporaryDirectory(prefix="webgl1-diagnostic-profile-") as directory:
            profile = Path(directory) / "dedicated-profile"
            profile.mkdir(mode=0o700)
            marker = profile / "synthetic-marker"
            marker.write_text("fixture-only")
            before = sorted(path.name for path in profile.iterdir())

            resolved = runner.validate_profile_dir(profile)
            launch = runner.family1_launch_configuration(Path("/synthetic/Chromium"), resolved)

            self.assertEqual(resolved, profile.absolute())
            self.assertIn(f"--user-data-dir={profile.absolute()}", launch["argv"])
            self.assertEqual(sorted(path.name for path in profile.iterdir()), before)

            with self.assertRaises(ValueError):
                runner.validate_profile_dir(profile, profile / "diagnostic-output")

    def test_profile_dir_requires_existing_real_directory(self):
        with tempfile.TemporaryDirectory(prefix="webgl1-diagnostic-profile-guards-") as directory:
            root = Path(directory)
            missing = root / "missing"
            plain_file = root / "plain-file"
            plain_file.write_text("fixture-only")
            target = root / "target"
            target.mkdir(mode=0o700)
            symlink = root / "directory-link"
            symlink.symlink_to(target, target_is_directory=True)

            for invalid in (missing, plain_file, symlink):
                with self.subTest(invalid=invalid.name):
                    with self.assertRaises(ValueError):
                        runner.validate_profile_dir(invalid)

    def test_page_has_bounded_ordered_real_webgl_stages_without_fallbacks(self):
        nonce = "a" * 32
        html = runner.diagnostic_page(nonce).decode("utf-8")
        expected = ("initial-triangle-raw-readback", "default-clear", "scissor-clear", "vbo-triangle",
                    "uniform-color-triangle", "constant-attribute-point",
                    "offscreen-fbo-clear", "offscreen-fbo-triangle",
                    "single-sample-clear-vbo", "single-sample-constant-point",
                    "single-sample-vbo-point-packed", "single-sample-vbo-point-interleaved",
                    "single-sample-vbo-triangle-vec4-stride16",
                    "single-sample-vbo-triangle-vec2-subdata",
                    "single-sample-vbo-triangle-vec2-in-clip",
                    "single-sample-vbo-points-vec2-in-clip")
        positions = [html.index(f'"{name}"') for name in expected]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(len(expected), 16)
        call_positions=[html.index(f"stage(gl,'{name}'") for name in expected[:8]]
        call_positions += [html.index(f"stage(single,'{name}'") for name in expected[8:]]
        self.assertEqual(call_positions, sorted(call_positions))
        self.assertIn("result.before_finish_pixel=Array.from(pixel)",html)
        self.assertIn("result.after_finish_pixel=Array.from(pixel)",html)
        self.assertIn("0.0,160.0/255.0,0.0,1.0",html)
        self.assertIn("gl.vertexAttrib4f(location,1.0/96.0,1.0/96.0,0.0,1.0)",html)
        self.assertIn("gl.disableVertexAttribArray(location)",html)
        initial_draw=html.index("stage(gl,'initial-triangle-raw-readback'")
        viewport=html.index("gl.viewport(0,0,canvas.width,canvas.height)",initial_draw)
        draw=html.index("gl.drawArrays(gl.TRIANGLES,0,3)",initial_draw)
        self.assertLess(viewport,draw)
        self.assertIn("Number.isSafeInteger(queriedAttributes)",html)
        self.assertIn("Math.min(queriedAttributes,32)",html)
        for required in ("gl.VERTEX_ATTRIB_ARRAY_ENABLED", "gl.VERTEX_ATTRIB_ARRAY_SIZE",
                         "gl.VERTEX_ATTRIB_ARRAY_TYPE", "gl.VERTEX_ATTRIB_ARRAY_NORMALIZED",
                         "gl.VERTEX_ATTRIB_ARRAY_STRIDE", "gl.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING",
                         "getVertexAttribOffset", "single.CURRENT_VERTEX_ATTRIB",
                         "gl.bufferSubData(gl.ARRAY_BUFFER,0,vertices)",
                         "new Float32Array([1.0/32.0,1.0/32.0,0.5])",
                         "new Float32Array([-1,-1,0,1, 3,-1,0,1, -1,3,0,1])",
                         "new Float32Array([-0.75,-0.75, 0.75,-0.75, 0,0.75])",
                         "gl_PointSize=8.0"):
            self.assertIn(required,html)
        self.assertIn("addSkippedMatrixStages('single-sample-context-unavailable')",html)
        self.assertIn("addSkippedMatrixStages('prior-context-loss-or-fatal-gl-error')",html)
        for required in ("getContext('webgl'", "preserveDrawingBuffer:true",
                         "failIfMajorPerformanceCaveat:true", "gl.clear(",
                         "gl.enable(gl.SCISSOR_TEST)", "getAttribLocation",
                         "getBufferParameter(gl.ARRAY_BUFFER,gl.BUFFER_SIZE)",
                         "getUniformLocation", "gl.uniform4f", "gl.POINTS",
                         "gl.checkFramebufferStatus", "gl.RGBA,16,16,0,gl.RGBA,gl.UNSIGNED_BYTE",
                         "gl.finish()", "gl.isContextLost()", "gl.OUT_OF_MEMORY",
                         "antialias:true", "antialias:false", "gl.SAMPLE_BUFFERS",
                         "gl.SAMPLES", "single_sample_count",
                         "boundedLog(gl.getShaderInfoLog", "boundedLog(gl.getProgramInfoLog"):
            self.assertIn(required, html)
        self.assertIn("prior.out_of_memory || prior.context_lost",html)
        self.assertIn("prior-context-loss-or-fatal-gl-error",html)
        self.assertIn("if (state.stopped || contextLost(gl))",html)
        self.assertIn("diagnostic_only:true", html)
        self.assertIn("draw_call_issued", html)
        self.assertIn("details.draw_parameters={mode:null,first:null,count:null}",html)
        self.assertIn("captureRasterState(gl)",html)
        self.assertNotIn("draw_ok", html)
        self.assertNotIn("getContext('2d'", html)
        self.assertNotIn("getContext(\"webgl2\"", html)
        self.assertNotIn("getExtension(", html)
        self.assertNotIn("background:rgb(", html)
        self.assertIn(nonce, html)

    def test_embedded_javascript_passes_node_syntax_check_when_available(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is unavailable for the optional JavaScript syntax check")
        html = runner.diagnostic_page("b" * 32).decode("utf-8")
        script = html.split("<script>", 1)[1].split("</script>", 1)[0]
        with tempfile.TemporaryDirectory(prefix="webgl1-diagnostic-js-") as temp:
            path = Path(temp) / "fixture.js"
            path.write_text(script)
            checked = subprocess.run([node, "--check", str(path)], text=True,
                                     capture_output=True, check=False)
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_normalization_is_allowlisted_and_bounded(self):
        nonce = "c" * 32
        raw = {"nonce": nonce, "diagnostic_only": True, "context_ok": True,
               "context_lost": False, "stopped": False, "diagnostic_complete": True,
               "context_attributes":{"alpha":False,"antialias":False,
                   "depth":False,"preserveDrawingBuffer":True},
               "sample_buffers":1,"samples":4,
               "gl_version": "v" * 900, "glsl_version": "s" * 900,
               "private_unexpected_field": "do not retain",
               "stages": [{"name": name, "status": "passed", "checks":{"ok":True},
                           "gl_errors":[{"code":1282,"name":["malformed"]}],
                           "prior_gl_errors":[],
                           "pixel":[0,255,0,255], "expected_pixel":[0,255,0,255],
                           "before_finish_pixel":[0,160,0,255],
                           "after_finish_pixel":[0,160,0,255],
                           "details":{"draw_parameters":{"mode":None,"first":None,"count":None},
                                   "raster_state":{"viewport":[0,0,32,32],
                                       "scissor_enabled":False,"scissor_box":[0,0,32,32],
                                       "cull_enabled":False,"front_face":2305,"cull_mode":1029,
                                       "depth_enabled":False,"depth_func":513,
                                       "depth_write_mask":True,"stencil_enabled":False,
                                       "blend_enabled":False,"sample_buffers":0,"samples":0},
                                   "vertex_shader":{"compile_ok":True,
                              "info_log":"x"*6000}, "array_buffer_bytes":24,
                                   "untrusted_large_integer":2**100,
                                   "attribute_state":{"enabled":True,"size":2,"type":5126,
                                       "normalized":False,"stride":0,
                                       "buffer_binding_matches":True,"offset":0,
                                       "buffer_object":{"private":"never serialize"}},
                                   "current_attribute":[1.0/32.0,1.0/32.0,0.0,1.0]}}
                          for name in runner.STAGE_NAMES]}
        normalized = runner.normalize_state(raw, nonce)
        self.assertTrue(normalized["state_valid"])
        self.assertTrue(normalized["diagnostic_complete"])
        self.assertEqual(len(normalized["gl_version"]), 512)
        self.assertEqual(len(normalized["stages"][0]["details"]["vertex_shader"]["info_log"]),
                         runner.MAX_SHADER_LOG)
        self.assertEqual(normalized["context_attributes"]["antialias"], False)
        self.assertEqual(normalized["samples"], 4)
        self.assertEqual(normalized["stages"][0]["before_finish_pixel"],[0,160,0,255])
        self.assertEqual(normalized["stages"][0]["gl_errors"][0]["name"],"")
        self.assertNotIn("untrusted_large_integer",normalized["stages"][0]["details"])
        self.assertEqual(normalized["stages"][0]["details"]["attribute_state"],
            {"enabled":True,"size":2,"type":5126,"normalized":False,"stride":0,
             "buffer_binding_matches":True,"offset":0})
        self.assertEqual(normalized["stages"][0]["details"]["current_attribute"],
                         [1.0/32.0,1.0/32.0,0.0,1.0])
        self.assertNotIn("buffer_object",normalized["stages"][0]["details"]["attribute_state"])
        self.assertNotIn("private_unexpected_field", normalized)
        self.assertEqual(runner.diagnostic_classification(normalized, nonce, True),
                         "WEBGL1_DIAGNOSTIC_CAPTURED_REVIEW_PENDING")
        self.assertNotIn("pass", normalized)
        self.assertNotIn("accepted", runner.diagnostic_classification(normalized, nonce, True).lower())
        self.assertEqual(runner.diagnostic_classification(normalized,nonce,True,False),
                         "WEBGL1_DIAGNOSTIC_CAPTURE_INCOMPLETE")

    def test_draw_and_raster_metadata_is_allowlisted_bounded_and_malformed_safe(self):
        nonce="d"*32
        raster={"viewport":[0,0,32,32],"scissor_enabled":False,"scissor_box":[0,0,32,32],
            "cull_enabled":False,"front_face":2305,"cull_mode":1029,"depth_enabled":False,
            "depth_func":513,"depth_write_mask":True,"stencil_enabled":False,
            "blend_enabled":False,"sample_buffers":0,"samples":0}
        parameters={"mode":"POINTS","first":0,"count":3}
        stages=[{"name":name,"status":"passed","checks":{"ok":True},
            "gl_errors":[],"prior_gl_errors":[],"details":{"draw_parameters":parameters,
            "raster_state":raster,"untrusted_large_integer":2**100}} for name in runner.STAGE_NAMES]
        stages[1]["details"]["draw_parameters"]={"mode":None,"first":None,"count":None}
        raw={"nonce":nonce,"diagnostic_only":True,"context_ok":True,"context_lost":False,
             "stopped":False,"diagnostic_complete":True,"stages":stages}
        normalized=runner.normalize_state(raw,nonce)
        self.assertTrue(normalized["diagnostic_complete"])
        self.assertEqual(normalized["stage_count"],16)
        details=normalized["stages"][0]["details"]
        self.assertEqual(details["draw_parameters"],parameters)
        self.assertEqual(details["raster_state"],raster)
        self.assertNotIn("untrusted_large_integer",details)
        self.assertEqual(normalized["stages"][1]["details"]["draw_parameters"],
                         {"mode":None,"first":None,"count":None})

        malformed=copy.deepcopy(raw)
        malformed["stages"][0]["details"]["draw_parameters"]["count"]=runner.MAX_DRAW_VERTEX_COUNT+1
        malformed["stages"][0]["details"]["raster_state"]["viewport"]=[0,0,10**9,32]
        malformed_normalized=runner.normalize_state(malformed,nonce)
        sanitized=malformed_normalized["stages"][0]["details"]
        self.assertNotIn("draw_parameters",sanitized)
        self.assertNotIn("raster_state",sanitized)
        self.assertFalse(malformed_normalized["diagnostic_complete"])

        malformed["stages"][0]["details"]["draw_parameters"]={"mode":[],"first":False,"count":3}
        malformed["stages"][0]["details"]["raster_state"]={**raster,"extra":"discard"}
        sanitized=runner.normalize_state(malformed,nonce)["stages"][0]["details"]
        self.assertNotIn("draw_parameters",sanitized)
        self.assertNotIn("raster_state",sanitized)

        for enum_key in ("front_face","cull_mode","depth_func"):
            with self.subTest(enum_key=enum_key):
                malformed_enum=copy.deepcopy(raw)
                malformed_enum["stages"][0]["details"]["raster_state"][enum_key]=9999
                enum_normalized=runner.normalize_state(malformed_enum,nonce)
                self.assertNotIn("raster_state",enum_normalized["stages"][0]["details"])
                self.assertFalse(enum_normalized["diagnostic_complete"])

    def test_malformed_cdp_value_is_incomplete_not_an_exception(self):
        class FakeCdp:
            def call(self,*_args,**_kwargs):
                return {"result":{"value":["unexpected"]}}
        nonce="a"*32
        expected=f"http://127.0.0.1:43210/{nonce}/webgl1-diagnostic.html"
        snapshot=runner.read_state(FakeCdp(),nonce,expected)
        self.assertFalse(snapshot["document_ok"])
        self.assertFalse(snapshot["state"]["state_valid"])

    def test_state_wait_ignores_provisional_marker_and_waits_for_terminal_nonce(self):
        nonce="c"*32
        self.assertFalse(runner.diagnostic_state_ready({},nonce))
        self.assertFalse(runner.diagnostic_state_ready(
            {"js_marker":"WEBGL1_DIAGNOSTIC_PENDING","state":{"error":"invalid-state"}},nonce))
        for status in ("COMPLETE","INCOMPLETE","ERROR"):
            snapshot={"js_marker":f"WEBGL1_DIAGNOSTIC_{status}_{nonce}"}
            self.assertTrue(runner.diagnostic_state_ready(snapshot,nonce))
            self.assertFalse(runner.diagnostic_state_ready(
                {"js_marker":f"WEBGL1_DIAGNOSTIC_{status}_{'d'*32}"},nonce))

    def test_current_attribute_normalization_rejects_unsafe_numbers(self):
        nonce="b"*32
        for component in (2**4000,float("nan"),float("inf"),True):
            state={"nonce":nonce,"diagnostic_only":True,"context_ok":True,
                   "stages":[{"name":runner.STAGE_NAMES[0],
                       "details":{"current_attribute":[0.0,0.0,component,1.0]}}]}
            normalized=runner.normalize_state(state,nonce)
            self.assertNotIn("current_attribute",normalized["stages"][0]["details"])

    def test_invalid_null_wrong_nonce_and_missing_marker_are_incomplete(self):
        nonce = "d" * 32
        self.assertEqual(runner.normalize_state({"nonce":"wrong"}, nonce)["error"],
                         "invalid-state")
        wrong=runner.normalize_state({"nonce":"wrong","diagnostic_only":True},nonce)
        self.assertFalse(wrong["state_valid"])
        self.assertEqual(runner.diagnostic_classification(wrong,nonce,True),
                         "WEBGL1_DIAGNOSTIC_CAPTURE_INCOMPLETE")
        self.assertFalse(runner.normalize_state(None,nonce)["state_valid"])
        missing_marker=runner.normalize_state({"nonce":nonce,"context_ok":True,
            "stages":[]},nonce)
        self.assertFalse(missing_marker["state_valid"])
        self.assertEqual(runner.diagnostic_classification(None, nonce, True),
                         "WEBGL1_DIAGNOSTIC_CAPTURE_INCOMPLETE")

    def test_duplicate_out_of_order_or_unknown_stages_are_never_complete(self):
        nonce="f"*32
        for names in (list(runner.STAGE_NAMES[:-1])+[runner.STAGE_NAMES[-2]],
                      list(reversed(runner.STAGE_NAMES)),
                      list(runner.STAGE_NAMES)+["unknown"]):
            state={"nonce":nonce,"diagnostic_only":True,"context_ok":True,
                   "diagnostic_complete":True,
                   "stages":[{"name":name,"status":"passed"} for name in names]}
            self.assertFalse(runner.normalize_state(state,nonce)["diagnostic_complete"])

    def test_fixture_document_url_requires_exact_loopback_nonce_path(self):
        nonce="9"*32
        expected=f"http://127.0.0.1:43123/{nonce}/webgl1-diagnostic.html"
        self.assertTrue(runner.fixture_url_is_valid(expected,expected,nonce))
        for bad in (expected.replace(nonce,"8"*32),
                    expected.replace("127.0.0.1","localhost"),
                    expected+"?x=1",expected+"#fragment",
                    "https://127.0.0.1:43123/"+nonce+"/webgl1-diagnostic.html",
                    f"http://127.0.0.1/{nonce}/webgl1-diagnostic.html"):
            self.assertFalse(runner.fixture_url_is_valid(bad,expected,nonce),bad)

    def test_invalid_bounds_and_existing_output_refuse_before_host_inspection(self):
        with tempfile.TemporaryDirectory(prefix="webgl1-diagnostic-guards-") as directory:
            output = Path(directory) / "fresh-output"
            args = SimpleNamespace(startup_timeout=4, navigation_timeout=60,
                                   observe_seconds=10, out=str(output), app="/synthetic/app")
            with patch.object(runner.probe, "mac_context") as context, \
                    patch.object(runner.probe, "app_executable") as app:
                with self.assertRaises(ValueError):
                    runner.run(args)
                context.assert_not_called(); app.assert_not_called()
            self.assertFalse(output.exists())

            output.mkdir()
            args.startup_timeout = 45
            with patch.object(runner.probe, "mac_context") as context, \
                    patch.object(runner.probe, "app_executable") as app:
                with self.assertRaises(FileExistsError):
                    runner.run(args)
                context.assert_not_called(); app.assert_not_called()

    def test_fixture_routes_only_the_nonce_diagnostic_document(self):
        nonce = "e" * 32
        page = runner.diagnostic_page(nonce)
        status, content_type, payload = runner.fixture_response(
            nonce, page, f"/{nonce}/webgl1-diagnostic.html")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html; charset=utf-8")
        self.assertIn(nonce.encode(), payload)
        self.assertEqual(runner.fixture_response(nonce, page, "/other"),
                         (404, "text/plain", b"not found"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
