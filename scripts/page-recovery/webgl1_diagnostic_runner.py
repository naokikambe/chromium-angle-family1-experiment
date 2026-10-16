#!/usr/bin/env python3
"""Capture bounded, stage-by-stage WebGL1 diagnostics on a dedicated profile.

This diagnostic runner is separate from webgl1_runner.py's acceptance fixture.
Its results can locate a failure boundary but never establish WebGL or product
acceptance. It does not modify or sign the app bundle. An existing dedicated
test profile can be explicitly reused with --profile-dir.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import http.server
import io
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import threading
import time
import urllib.parse
import uuid

import probe
import persistent_cookie_runner as cookie_runner
import webgl1_runner as accepted_runner


FAMILY1_ARGUMENTS = accepted_runner.FAMILY1_ARGUMENTS
OPT_IN_ENV = accepted_runner.OPT_IN_ENV
STAGE_NAMES = (
    "initial-triangle-raw-readback",
    "default-clear",
    "scissor-clear",
    "vbo-triangle",
    "uniform-color-triangle",
    "constant-attribute-point",
    "offscreen-fbo-clear",
    "offscreen-fbo-triangle",
    "single-sample-clear-vbo",
    "single-sample-constant-point",
    "single-sample-vbo-point-packed",
    "single-sample-vbo-point-interleaved",
    "single-sample-vbo-triangle-vec4-stride16",
    "single-sample-vbo-triangle-vec2-subdata",
    "single-sample-vbo-triangle-vec2-in-clip",
    "single-sample-vbo-points-vec2-in-clip",
    "single-sample-vbo-point-vec2-in-clip-first-0",
    "single-sample-vbo-point-vec2-in-clip-first-1",
    "single-sample-vbo-point-vec2-in-clip-first-2",
    "single-sample-vbo-point-vec2-in-clip-first-0-centerline",
    "single-sample-vbo-point-vec2-in-clip-first-1-centerline",
    "single-sample-vbo-point-vec2-in-clip-first-2-centerline",
)
MAX_STAGE_COUNT = len(STAGE_NAMES)
MAX_GL_ERRORS_PER_STAGE = 16
MAX_SHADER_LOG = 4096
MAX_HTTP_EVENTS = 32
MAX_DRAW_VERTEX_COUNT = 1_000_000
MAX_RASTER_COORDINATE = 1_000_000


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def validate_options(startup_timeout, navigation_timeout, observe_seconds):
    accepted_runner.validate_options(startup_timeout, navigation_timeout, observe_seconds)


def validate_profile_dir(profile_dir, output_dir=None):
    """Resolve an optional, already-created dedicated profile without creating it."""
    if profile_dir is None:
        return None
    profile = Path(profile_dir).expanduser().absolute()
    if profile.is_symlink() or not profile.is_dir():
        raise ValueError("profile-dir must be an existing, non-symlink directory")
    profile_stat = profile.stat()
    if profile_stat.st_uid != os.getuid() or stat.S_IMODE(profile_stat.st_mode) & 0o077:
        raise ValueError("profile-dir must be owned by the current user and private")
    if output_dir is not None:
        output = Path(output_dir).expanduser().absolute()
        if profile == output or profile in output.parents:
            raise ValueError("diagnostic output must be outside the reused profile")
    if any((profile / name).exists() or (profile / name).is_symlink()
           for name in ("SingletonLock", "SingletonSocket")):
        raise ValueError("profile-dir appears to be in use")
    return profile


def family1_launch_configuration(executable, profile):
    return cookie_runner.browser_launch_configuration(executable, profile, FAMILY1_ARGUMENTS, "1")


def diagnostic_page(nonce):
    """Return a fixed ES 1.00 WebGL1 staged diagnostic; no visual fallback."""
    template = r"""<!doctype html><meta charset=utf-8>
<title>PHASE5_WEBGL1_DIAGNOSTIC___NONCE__</title>
<style>body{font:16px sans-serif;background:#fff;color:#111}canvas{width:96px;height:96px;border:1px solid #555}</style>
<h1 id="body-marker">WEBGL1_DIAGNOSTIC_BODY___NONCE__</h1>
<p id="js-marker">WEBGL1_DIAGNOSTIC_PENDING</p>
<ol id="stage-list"></ol>
<canvas id="webgl-canvas" width="96" height="96"></canvas>
<p>Antialias-disabled comparison canvas:</p>
<canvas id="single-sample-canvas" width="32" height="32"></canvas>
<script>
(() => {
  const nonce = __NONCE_JSON__;
  const names = ["initial-triangle-raw-readback","default-clear","scissor-clear","vbo-triangle",
    "uniform-color-triangle","constant-attribute-point",
    "offscreen-fbo-clear","offscreen-fbo-triangle","single-sample-clear-vbo",
    "single-sample-constant-point","single-sample-vbo-point-packed",
    "single-sample-vbo-point-interleaved","single-sample-vbo-triangle-vec4-stride16",
    "single-sample-vbo-triangle-vec2-subdata","single-sample-vbo-triangle-vec2-in-clip",
    "single-sample-vbo-points-vec2-in-clip",
    "single-sample-vbo-point-vec2-in-clip-first-0",
    "single-sample-vbo-point-vec2-in-clip-first-1",
    "single-sample-vbo-point-vec2-in-clip-first-2",
    "single-sample-vbo-point-vec2-in-clip-first-0-centerline",
    "single-sample-vbo-point-vec2-in-clip-first-1-centerline",
    "single-sample-vbo-point-vec2-in-clip-first-2-centerline"];
  const matrixNames=names.slice(9);
  const state = {nonce, diagnostic_only:true, context_ok:false, context_lost:false,
    stopped:false, stages:[], gl_version:null, glsl_version:null, error:null,
    context_attributes:null,sample_buffers:null,samples:null,
    single_sample_context_attributes:null,single_sample_buffers:null,single_sample_count:null};
  const canvas = document.getElementById('webgl-canvas');
  const singleCanvas = document.getElementById('single-sample-canvas');
  const list = document.getElementById('stage-list');
  const errors = [
    [0x0500,'INVALID_ENUM'],[0x0501,'INVALID_VALUE'],[0x0502,'INVALID_OPERATION'],
    [0x0505,'OUT_OF_MEMORY'],[0x0506,'INVALID_FRAMEBUFFER_OPERATION'],
    [0x9242,'CONTEXT_LOST_WEBGL']];
  const errorName = code => (errors.find(entry => entry[0] === code) || [0,'UNKNOWN_GL_ERROR'])[1];
  const boundedLog = value => String(value || '').slice(0,4096);
  const contextLost = gl => {
    state.context_lost = Boolean(state.context_lost || gl.isContextLost());
    return state.context_lost;
  };
  canvas.addEventListener('webglcontextlost', event => {
    event.preventDefault(); state.context_lost = true; state.stopped = true;
  }, {once:true});
  function drainErrors(gl) {
    const out = [];
    let out_of_memory=false, context_lost=false, truncated=false;
    for (let i=0; i<64; ++i) {
      const code = gl.getError();
      if (code === gl.NO_ERROR) break;
      if (code===gl.OUT_OF_MEMORY) out_of_memory=true;
      if (code===0x9242) context_lost=true;
      if (out.length<16) out.push({code, name:errorName(code)});
      else truncated=true;
    }
    return {errors:out,out_of_memory,context_lost,truncated};
  }
  function resetDefault(gl, targetCanvas=canvas) {
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.useProgram(null);
    gl.bindBuffer(gl.ARRAY_BUFFER, null); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, null);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, null);
    gl.disable(gl.SCISSOR_TEST); gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.STENCIL_TEST); gl.disable(gl.CULL_FACE); gl.colorMask(true,true,true,true);
    const queriedAttributes=gl.getParameter(gl.MAX_VERTEX_ATTRIBS);
    const maxAttributes=Number.isSafeInteger(queriedAttributes) && queriedAttributes>=0
      ? Math.min(queriedAttributes,32) : 0;
    for (let index=0; index<maxAttributes; ++index) {
      gl.disableVertexAttribArray(index); gl.vertexAttrib4f(index,0,0,0,1);
    }
    gl.viewport(0,0,targetCanvas.width,targetCanvas.height);
    gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT);
  }
  function pixelAt(gl, x, y) {
    gl.finish();
    const pixel = new Uint8Array(4);
    gl.readPixels(x,y,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
    return Array.from(pixel);
  }
  function addStage(stage) {
    if (!stage.details || typeof stage.details !== 'object') stage.details={};
    if (!Object.prototype.hasOwnProperty.call(stage.details,'draw_parameters'))
      stage.details.draw_parameters={mode:null,first:null,count:null};
    if (!Object.prototype.hasOwnProperty.call(stage.details,'raster_state'))
      stage.details.raster_state=null;
    state.stages.push(stage);
    const item = document.createElement('li');
    item.textContent = stage.name + ': ' + stage.status +
      (stage.pixel ? ' pixel=' + stage.pixel.join(',') : '') +
      (stage.before_finish_pixel ? ' before-finish=' + stage.before_finish_pixel.join(',') : '') +
      (stage.after_finish_pixel ? ' after-finish=' + stage.after_finish_pixel.join(',') : '') +
      (stage.gl_errors.length ? ' GL_ERROR' : '');
    list.appendChild(item);
  }
  function addSkippedMatrixStages(reason) {
    for (const name of matrixNames) {
      addStage({name,status:'skipped',checks:{},gl_errors:[],prior_gl_errors:[],
        pixel:null,expected_pixel:null,details:{reason}});
    }
  }
  function captureRasterState(gl) {
    const viewport=Array.from(gl.getParameter(gl.VIEWPORT)||[]);
    const scissorBox=Array.from(gl.getParameter(gl.SCISSOR_BOX)||[]);
    return {
      viewport:viewport.slice(0,4),scissor_enabled:gl.isEnabled(gl.SCISSOR_TEST),
      scissor_box:scissorBox.slice(0,4),cull_enabled:gl.isEnabled(gl.CULL_FACE),
      front_face:gl.getParameter(gl.FRONT_FACE),cull_mode:gl.getParameter(gl.CULL_FACE_MODE),
      depth_enabled:gl.isEnabled(gl.DEPTH_TEST),depth_func:gl.getParameter(gl.DEPTH_FUNC),
      depth_write_mask:gl.getParameter(gl.DEPTH_WRITEMASK),
      stencil_enabled:gl.isEnabled(gl.STENCIL_TEST),blend_enabled:gl.isEnabled(gl.BLEND),
      sample_buffers:gl.getParameter(gl.SAMPLE_BUFFERS),samples:gl.getParameter(gl.SAMPLES)
    };
  }
  function setDrawParameters(gl,result,mode,first,count) {
    result.details.draw_parameters={mode,first,count};
    result.details.raster_state=captureRasterState(gl);
  }
  function stage(gl, name, operation) {
    if (state.stopped || contextLost(gl)) {
      addStage({name,status:'skipped',checks:{},gl_errors:[],prior_gl_errors:[],
        pixel:null,expected_pixel:null,details:{reason:'context-lost-or-fatal'}});
      return;
    }
    const result = {name,status:'failed',checks:{},gl_errors:[],prior_gl_errors:[],
      pixel:null,expected_pixel:null,details:{draw_parameters:{mode:null,first:null,count:null}}};
    const prior = drainErrors(gl);
    result.prior_gl_errors = prior.errors;
    if (prior.truncated) result.details.prior_errors_truncated=true;
    if (prior.out_of_memory || prior.context_lost || prior.truncated) {
      result.details.prior_fatal_gl_error=true;
      if (prior.out_of_memory) result.details.out_of_memory=true;
      if (prior.context_lost) result.details.context_lost=true;
      state.stopped=true;
      if (prior.context_lost) state.context_lost=true;
      addStage(result);
      return;
    }
    try {
      result.details.raster_state=captureRasterState(gl);
      operation(result);
      gl.finish();
    } catch (error) {
      result.details.exception = String(error && error.name || 'Error').slice(0,64);
    }
    const after = drainErrors(gl);
    result.gl_errors = after.errors;
    if (after.truncated) result.details.gl_errors_truncated=true;
    if (contextLost(gl)) {
      result.details.context_lost = true;
      state.stopped = true;
    }
    if (after.out_of_memory) {
      result.details.out_of_memory = true;
      state.stopped = true;
    }
    if (after.context_lost) {
      result.details.context_lost = true;
      state.context_lost=true; state.stopped=true;
    }
    const checks = Object.values(result.checks);
    result.status = (!state.context_lost && !state.stopped && !result.details.exception &&
      result.gl_errors.length === 0 && !after.truncated && checks.length > 0 && checks.every(value => value === true))
      ? 'passed' : 'failed';
    addStage(result);
  }
  function compileProgram(gl, vertexSource, fragmentSource, result) {
    const compile = (kind, source) => {
      const shader = gl.createShader(kind);
      if (!shader) throw new Error('shader-allocation-failed');
      gl.shaderSource(shader, source); gl.compileShader(shader);
      const ok = gl.getShaderParameter(shader, gl.COMPILE_STATUS) === true;
      result.details[kind === gl.VERTEX_SHADER ? 'vertex_shader' : 'fragment_shader'] = {
        compile_ok:ok, info_log:boundedLog(gl.getShaderInfoLog(shader))};
      return {shader,ok};
    };
    const vertex = compile(gl.VERTEX_SHADER, vertexSource);
    const fragment = compile(gl.FRAGMENT_SHADER, fragmentSource);
    result.checks.vertex_compile = vertex.ok;
    result.checks.fragment_compile = fragment.ok;
    if (!vertex.ok || !fragment.ok) return null;
    const program = gl.createProgram();
    if (!program) throw new Error('program-allocation-failed');
    gl.attachShader(program,vertex.shader); gl.attachShader(program,fragment.shader);
    gl.linkProgram(program);
    const linked = gl.getProgramParameter(program,gl.LINK_STATUS) === true;
    result.details.program = {link_ok:linked,info_log:boundedLog(gl.getProgramInfoLog(program))};
    result.checks.program_link = linked;
    return linked ? program : null;
  }
  function vbo(gl, program, result) {
    const location = gl.getAttribLocation(program,'a_position');
    result.details.attribute_location = location;
    result.checks.attribute_location_valid = location >= 0;
    if (location < 0) return false;
    const vertices = new Float32Array([-1,-1,3,-1,-1,3]);
    const buffer = gl.createBuffer();
    result.checks.buffer_created = Boolean(buffer);
    if (!buffer) return false;
    gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
    gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);
    const bytes = gl.getBufferParameter(gl.ARRAY_BUFFER,gl.BUFFER_SIZE);
    result.details.array_buffer_bytes = bytes;
    result.checks.array_buffer_size_matches = bytes === vertices.byteLength;
    if (!result.checks.array_buffer_size_matches) return false;
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location,2,gl.FLOAT,false,0,0);
    return true;
  }
  function captureAttributeState(gl,location,expectedBuffer,result,expectations={}) {
    const binding=gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING);
    const state={
      enabled:gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_ENABLED)===true,
      size:gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_SIZE),
      type:gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_TYPE),
      normalized:gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_NORMALIZED)===true,
      stride:gl.getVertexAttrib(location,gl.VERTEX_ATTRIB_ARRAY_STRIDE),
      buffer_binding_matches:binding===expectedBuffer,
      offset:gl.getVertexAttribOffset(location,gl.VERTEX_ATTRIB_ARRAY_POINTER)
    };
    result.details.attribute_state=state;
    result.checks.attribute_enabled=state.enabled===expectations.enabled;
    for (const key of ['size','type','normalized','stride','buffer_binding_matches','offset']) {
      if (Object.prototype.hasOwnProperty.call(expectations,key))
        result.checks['attribute_'+key]=state[key]===expectations[key];
    }
    return state;
  }
  function matrixBuffer(gl,program,result,vertices,components,stride,offset,uploadPath) {
    const location=gl.getAttribLocation(program,'a_position');
    result.details.attribute_location=location;
    result.checks.attribute_location_valid=location>=0;
    if (location<0) return null;
    const buffer=gl.createBuffer();
    result.checks.buffer_created=Boolean(buffer);
    if (!buffer) return null;
    gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
    if (uploadPath==='bufferData-size+bufferSubData') {
      gl.bufferData(gl.ARRAY_BUFFER,vertices.byteLength,gl.STATIC_DRAW);
      gl.bufferSubData(gl.ARRAY_BUFFER,0,vertices);
    } else {
      gl.bufferData(gl.ARRAY_BUFFER,vertices,gl.STATIC_DRAW);
    }
    const bytes=gl.getBufferParameter(gl.ARRAY_BUFFER,gl.BUFFER_SIZE);
    result.details.buffer_bytes=bytes;
    result.details.upload_path=uploadPath;
    result.checks.buffer_bytes_match=bytes===vertices.byteLength;
    if (!result.checks.buffer_bytes_match) return null;
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location,components,gl.FLOAT,false,stride,offset);
    const state=captureAttributeState(gl,location,buffer,result,
      {enabled:true,size:components,type:gl.FLOAT,normalized:false,stride,
       buffer_binding_matches:true,offset});
    result.checks.attribute_state_valid=Object.values(result.checks).every(value=>value===true);
    return {location,buffer,state};
  }
  function drawMatrixTriangle(gl,result,vertices,components,stride,offset,uploadPath) {
    resetDefault(gl,singleCanvas);
    const vertex=components===4
      ? 'attribute vec4 a_position; void main(){gl_Position=a_position;}'
      : 'attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);}';
    const program=compileProgram(gl,vertex,
      'precision mediump float; void main(){gl_FragColor=vec4(0.0,1.0,0.0,1.0);}',result);
    if (!program || !matrixBuffer(gl,program,result,vertices,components,stride,offset,uploadPath)) return;
    gl.useProgram(program); setDrawParameters(gl,result,'TRIANGLES',0,3);
    gl.drawArrays(gl.TRIANGLES,0,3);
    result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
    result.expected_pixel=[0,255,0,255]; result.pixel=pixelAt(gl,16,16);
    result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
  }
  function drawMatrixPoint(gl,result,vertices,stride,uploadPath) {
    resetDefault(gl,singleCanvas);
    const vertex='attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);gl_PointSize=8.0;}';
    const program=compileProgram(gl,vertex,
      'precision mediump float; void main(){gl_FragColor=vec4(1.0,1.0,0.0,1.0);}',result);
    if (!program || !matrixBuffer(gl,program,result,vertices,2,stride,0,uploadPath)) return;
    gl.useProgram(program); setDrawParameters(gl,result,'POINTS',0,1);
    gl.drawArrays(gl.POINTS,0,1);
    result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
    result.expected_pixel=[255,255,0,255]; result.pixel=pixelAt(gl,16,16);
    result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
  }
  function drawMatrixPoints(gl,result,vertices,components,stride,offset,uploadPath) {
    resetDefault(gl,singleCanvas);
    const vertex=components===2
      ? 'attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);gl_PointSize=8.0;}'
      : 'attribute vec4 a_position; void main(){gl_Position=a_position;gl_PointSize=8.0;}';
    const program=compileProgram(gl,vertex,
      'precision mediump float; void main(){gl_FragColor=vec4(1.0,1.0,0.0,1.0);}',result);
    if (!program || !matrixBuffer(gl,program,result,vertices,components,stride,offset,uploadPath)) return;
    gl.useProgram(program); setDrawParameters(gl,result,'POINTS',0,3);
    gl.drawArrays(gl.POINTS,0,3);
    result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
    result.expected_pixel=[255,255,0,255]; result.pixel=pixelAt(gl,16,28);
    result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
  }
  function drawMatrixPointAt(gl,result,vertices,first,x,y) {
    resetDefault(gl,singleCanvas);
    const vertex='attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);gl_PointSize=8.0;}';
    const program=compileProgram(gl,vertex,
      'precision mediump float; void main(){gl_FragColor=vec4(1.0,1.0,0.0,1.0);}',result);
    if (!program || !matrixBuffer(gl,program,result,vertices,2,0,0,'bufferData-float32-array')) return;
    gl.useProgram(program); setDrawParameters(gl,result,'POINTS',first,1);
    gl.drawArrays(gl.POINTS,first,1);
    result.details.vertex_index=first;
    result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
    result.expected_pixel=[255,255,0,255]; result.pixel=pixelAt(gl,x,y);
    result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
  }
  function drawVbo(gl, result, colorSource, uniformColor, targetCanvas=canvas) {
    resetDefault(gl,targetCanvas);
    const vertex = 'attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);}';
    const program = compileProgram(gl,vertex,colorSource,result);
    if (!program || !vbo(gl,program,result)) return;
    gl.useProgram(program);
    if (uniformColor) {
      const location = gl.getUniformLocation(program,'u_color');
      result.details.uniform_location_valid = location !== null;
      result.checks.uniform_location_valid = location !== null;
      if (location === null) return;
      gl.uniform4f(location,0,0,1,1);
    }
    setDrawParameters(gl,result,'TRIANGLES',0,3); gl.drawArrays(gl.TRIANGLES,0,3);
    result.details.draw_call_issued = true;
    result.checks.draw_call_issued = true;
    result.expected_pixel = uniformColor ? [0,0,255,255] : [0,255,0,255];
    result.pixel = pixelAt(gl,targetCanvas.width>>1,targetCanvas.height>>1);
    result.checks.readback_matches = result.pixel.every((value,index) => value === result.expected_pixel[index]);
  }
  function createOffscreen(gl,result) {
    const texture = gl.createTexture(), framebuffer = gl.createFramebuffer();
    result.checks.texture_created = Boolean(texture);
    result.checks.framebuffer_created = Boolean(framebuffer);
    if (!texture || !framebuffer) return null;
    gl.bindTexture(gl.TEXTURE_2D,texture);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,16,16,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
    gl.bindFramebuffer(gl.FRAMEBUFFER,framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,texture,0);
    const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
    result.details.framebuffer_status = status;
    result.details.framebuffer_complete = status === gl.FRAMEBUFFER_COMPLETE;
    result.checks.framebuffer_complete = status === gl.FRAMEBUFFER_COMPLETE;
    gl.viewport(0,0,16,16);
    return status === gl.FRAMEBUFFER_COMPLETE ? {texture,framebuffer} : null;
  }
  function run() {
    const gl = canvas.getContext('webgl',{preserveDrawingBuffer:true,alpha:false,antialias:true,
      failIfMajorPerformanceCaveat:true});
    if (!gl) { state.error='webgl-context-unavailable'; state.stopped=true; }
    else {
      state.context_ok=true;
      state.gl_version=String(gl.getParameter(gl.VERSION)||'').slice(0,512);
      state.glsl_version=String(gl.getParameter(gl.SHADING_LANGUAGE_VERSION)||'').slice(0,512);
      const attrs=gl.getContextAttributes()||{};
      state.context_attributes={alpha:attrs.alpha===true,antialias:attrs.antialias===true,
        depth:attrs.depth===true,stencil:attrs.stencil===true,
        premultipliedAlpha:attrs.premultipliedAlpha===true,
        preserveDrawingBuffer:attrs.preserveDrawingBuffer===true};
      state.sample_buffers=gl.getParameter(gl.SAMPLE_BUFFERS);
      state.samples=gl.getParameter(gl.SAMPLES);
      stage(gl,'initial-triangle-raw-readback',result => {
        const vertex='attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);}';
        const program=compileProgram(gl,vertex,
          'precision mediump float; void main(){gl_FragColor=vec4(0.0,160.0/255.0,0.0,1.0);}',result);
        if (!program || !vbo(gl,program,result)) return;
        gl.viewport(0,0,canvas.width,canvas.height);
        gl.useProgram(program); setDrawParameters(gl,result,'TRIANGLES',0,3);
        gl.drawArrays(gl.TRIANGLES,0,3);
        result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
        result.expected_pixel=[0,160,0,255];
        let pixel=new Uint8Array(4);
        gl.readPixels(48,48,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
        result.before_finish_pixel=Array.from(pixel);
        result.checks.before_finish_matches=result.before_finish_pixel.every(
          (v,i)=>v===result.expected_pixel[i]);
        gl.finish();
        pixel=new Uint8Array(4);
        gl.readPixels(48,48,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);
        result.after_finish_pixel=Array.from(pixel);
        result.checks.after_finish_matches=result.after_finish_pixel.every(
          (v,i)=>v===result.expected_pixel[i]);
      });
      stage(gl,'default-clear',result => {
        resetDefault(gl); result.details.raster_state=captureRasterState(gl);
        result.expected_pixel=[255,0,0,255];
        gl.clearColor(1,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT);
        result.pixel=pixelAt(gl,48,48);
        result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
      });
      stage(gl,'scissor-clear',result => {
        resetDefault(gl); gl.enable(gl.SCISSOR_TEST); gl.scissor(47,47,2,2);
        result.details.raster_state=captureRasterState(gl);
        gl.clearColor(0,0,1,1); gl.clear(gl.COLOR_BUFFER_BIT); gl.disable(gl.SCISSOR_TEST);
        result.expected_pixel=[0,0,255,255]; result.pixel=pixelAt(gl,48,48);
        result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
      });
      stage(gl,'vbo-triangle',result => drawVbo(gl,result,
        'precision mediump float; void main(){gl_FragColor=vec4(0.0,1.0,0.0,1.0);}',false));
      stage(gl,'uniform-color-triangle',result => drawVbo(gl,result,
        'precision mediump float; uniform vec4 u_color; void main(){gl_FragColor=u_color;}',true));
      stage(gl,'constant-attribute-point',result => {
        resetDefault(gl);
        const program=compileProgram(gl,
          'attribute vec4 a_position; void main(){gl_Position=a_position;gl_PointSize=1.0;}',
          'precision mediump float; void main(){gl_FragColor=vec4(1.0,1.0,0.0,1.0);}',result);
        if (!program) return;
        const location=gl.getAttribLocation(program,'a_position');
        result.details.attribute_location=location;
        result.checks.attribute_location_valid=location>=0;
        if (location<0) return;
        gl.useProgram(program); gl.disableVertexAttribArray(location);
        gl.vertexAttrib4f(location,1.0/96.0,1.0/96.0,0.0,1.0);
        result.details.constant_attribute_set=true;
        result.checks.constant_attribute_set=true;
        setDrawParameters(gl,result,'POINTS',0,1); gl.drawArrays(gl.POINTS,0,1);
        result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
        result.expected_pixel=[255,255,0,255]; result.pixel=pixelAt(gl,48,48);
        result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
      });
      stage(gl,'offscreen-fbo-clear',result => {
        resetDefault(gl); const target=createOffscreen(gl,result); if (!target) return;
        result.details.raster_state=captureRasterState(gl);
        result.expected_pixel=[255,0,255,255]; gl.clearColor(1,0,1,1);
        gl.clear(gl.COLOR_BUFFER_BIT); result.pixel=pixelAt(gl,8,8);
        result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
        gl.bindFramebuffer(gl.FRAMEBUFFER,null);
      });
      stage(gl,'offscreen-fbo-triangle',result => {
        resetDefault(gl); const target=createOffscreen(gl,result); if (!target) return;
        const vertex='attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);}';
        const program=compileProgram(gl,vertex,
          'precision mediump float; void main(){gl_FragColor=vec4(0.0,1.0,1.0,1.0);}',result);
        if (!program || !vbo(gl,program,result)) return;
        gl.useProgram(program); setDrawParameters(gl,result,'TRIANGLES',0,3);
        gl.drawArrays(gl.TRIANGLES,0,3);
        result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
        result.expected_pixel=[0,255,255,255]; result.pixel=pixelAt(gl,8,8);
        result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
        gl.bindFramebuffer(gl.FRAMEBUFFER,null);
      });
      if (state.stopped || contextLost(gl)) {
        addStage({name:'single-sample-clear-vbo',status:'skipped',checks:{},
          gl_errors:[],prior_gl_errors:[],pixel:null,expected_pixel:null,
          details:{reason:'prior-context-loss-or-fatal-gl-error'}});
        addSkippedMatrixStages('prior-context-loss-or-fatal-gl-error');
      } else {
      let single=null;
      try {
        single=singleCanvas.getContext('webgl',{preserveDrawingBuffer:true,alpha:false,
          antialias:false,failIfMajorPerformanceCaveat:true});
      } catch (_) {}
      if (!single) {
        addStage({name:'single-sample-clear-vbo',status:'failed',checks:{context_available:false},
          gl_errors:[],prior_gl_errors:[],pixel:null,expected_pixel:null,
          details:{context_unavailable:true,context_attributes_requested:{antialias:false}}});
        addSkippedMatrixStages('single-sample-context-unavailable');
      } else {
        singleCanvas.addEventListener('webglcontextlost', event => {
          event.preventDefault(); state.context_lost=true; state.stopped=true;
        }, {once:true});
        const attrs=single.getContextAttributes()||{};
        state.single_sample_context_attributes={alpha:attrs.alpha===true,
          antialias:attrs.antialias===true,preserveDrawingBuffer:attrs.preserveDrawingBuffer===true};
        state.single_sample_buffers=single.getParameter(single.SAMPLE_BUFFERS);
        state.single_sample_count=single.getParameter(single.SAMPLES);
        stage(single,'single-sample-clear-vbo',result => {
          resetDefault(single,singleCanvas);
          result.expected_clear_pixel=[255,0,0,255];
          single.clearColor(1,0,0,1); single.clear(single.COLOR_BUFFER_BIT);
          result.clear_pixel=pixelAt(single,16,16);
          result.checks.clear_readback_matches=result.clear_pixel.every(
            (v,i)=>v===result.expected_clear_pixel[i]);
          result.details.antialias_disabled=state.single_sample_context_attributes.antialias===false;
          result.checks.antialias_disabled=state.single_sample_context_attributes.antialias===false;
          result.details.sample_buffers=state.single_sample_buffers;
          result.details.samples=state.single_sample_count;
          result.checks.single_sample=(state.single_sample_buffers===0 && state.single_sample_count===0);
          const vertex='attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);}';
          const program=compileProgram(single,vertex,
            'precision mediump float; void main(){gl_FragColor=vec4(0.0,1.0,0.0,1.0);}',result);
          if (!program || !vbo(single,program,result)) return;
          single.useProgram(program); setDrawParameters(single,result,'TRIANGLES',0,3);
          single.drawArrays(single.TRIANGLES,0,3);
          result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
          result.expected_pixel=[0,255,0,255]; result.pixel=pixelAt(single,16,16);
          result.checks.draw_readback_matches=result.pixel.every(
            (v,i)=>v===result.expected_pixel[i]);
        });
        stage(single,'single-sample-constant-point',result => {
          resetDefault(single,singleCanvas);
          const program=compileProgram(single,
            'attribute vec2 a_position; void main(){gl_Position=vec4(a_position,0.0,1.0);gl_PointSize=8.0;}',
            'precision mediump float; void main(){gl_FragColor=vec4(1.0,1.0,0.0,1.0);}',result);
          if (!program) return;
          const location=single.getAttribLocation(program,'a_position');
          result.details.attribute_location=location;
          result.checks.attribute_location_valid=location>=0;
          if (location<0) return;
          single.useProgram(program); single.disableVertexAttribArray(location);
          single.vertexAttrib4f(location,1.0/32.0,1.0/32.0,0.0,1.0);
          const state=captureAttributeState(single,location,null,result,{enabled:false});
          const current=Array.from(single.getVertexAttrib(location,single.CURRENT_VERTEX_ATTRIB));
          result.details.current_attribute=current;
          result.checks.current_attribute_matches=current.length===4 &&
            current[0]===1.0/32.0 && current[1]===1.0/32.0 && current[2]===0 && current[3]===1;
          result.details.constant_attribute_set=true;
          result.checks.constant_attribute_set=true;
          setDrawParameters(single,result,'POINTS',0,1); single.drawArrays(single.POINTS,0,1);
          result.details.draw_call_issued=true; result.checks.draw_call_issued=true;
          result.expected_pixel=[255,255,0,255]; result.pixel=pixelAt(single,16,16);
          result.checks.readback_matches=result.pixel.every((v,i)=>v===result.expected_pixel[i]);
        });
        stage(single,'single-sample-vbo-point-packed',result => drawMatrixPoint(single,result,
          new Float32Array([1.0/32.0,1.0/32.0]),0,'bufferData-float32-array'));
        stage(single,'single-sample-vbo-point-interleaved',result => drawMatrixPoint(single,result,
          new Float32Array([1.0/32.0,1.0/32.0,0.5]),12,'bufferData-float32-interleaved'));
        stage(single,'single-sample-vbo-triangle-vec4-stride16',result =>
          drawMatrixTriangle(single,result,
            new Float32Array([-1,-1,0,1, 3,-1,0,1, -1,3,0,1]),4,16,0,
            'bufferData-float32-array'));
        stage(single,'single-sample-vbo-triangle-vec2-subdata',result =>
          drawMatrixTriangle(single,result,
            new Float32Array([-1,-1,3,-1,-1,3]),2,0,0,
            'bufferData-size+bufferSubData'));
        const inClipVec2Vertices=new Float32Array([-0.75,-0.75, 0.75,-0.75, 0,0.75]);
        stage(single,'single-sample-vbo-triangle-vec2-in-clip',result =>
          drawMatrixTriangle(single,result,inClipVec2Vertices,2,0,0,
            'bufferData-float32-array'));
        stage(single,'single-sample-vbo-points-vec2-in-clip',result =>
          drawMatrixPoints(single,result,inClipVec2Vertices,2,0,0,
            'bufferData-float32-array'));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-0',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,0,4,4));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-1',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,1,28,4));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-2',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,2,16,28));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-0-centerline',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,0,4,16));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-1-centerline',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,1,28,16));
        stage(single,'single-sample-vbo-point-vec2-in-clip-first-2-centerline',result =>
          drawMatrixPointAt(single,result,inClipVec2Vertices,2,16,16));
      }
      }
    }
    state.completed_stage_count=state.stages.length;
    state.stage_count=names.length;
    state.diagnostic_complete=state.context_ok && state.stages.length===names.length &&
      !state.context_lost && !state.stopped;
    window.__phase5_webgl1_diagnostic=state;
    document.getElementById('js-marker').textContent=state.diagnostic_complete ?
      'WEBGL1_DIAGNOSTIC_COMPLETE_'+nonce : 'WEBGL1_DIAGNOSTIC_INCOMPLETE_'+nonce;
  }
  try { run(); } catch (error) {
    state.error=String(error&&error.name||'Error').slice(0,64);
    state.stopped=true; state.completed_stage_count=state.stages.length;
    window.__phase5_webgl1_diagnostic=state;
    document.getElementById('js-marker').textContent='WEBGL1_DIAGNOSTIC_ERROR_'+nonce;
  }
})();
</script>"""
    return (template.replace("__NONCE__", nonce)
            .replace("__NONCE_JSON__", json.dumps(nonce))).encode("utf-8")


class DiagnosticFixtureHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        status, content_type, payload = fixture_response(self.server.nonce,self.server.page,path)
        with self.server.events_lock:
            if len(self.server.events)<MAX_HTTP_EVENTS:
                self.server.events.append({"observed_at": timestamp(),"nonce":self.server.nonce,
                                           "path":path[:256],"status":status})
            else:
                self.server.events_truncated=True
        self.send_response(status); self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(payload))); self.send_header("Cache-Control","no-store")
        self.end_headers(); self.wfile.write(payload)

    def log_message(self, *_):
        pass


class DiagnosticFixtureServer(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, nonce, page):
        self.nonce,self.page=nonce,page
        self.events,self.events_lock,self.events_truncated=[],threading.Lock(),False
        super().__init__(("127.0.0.1",0),DiagnosticFixtureHandler)


def fixture_response(nonce, page, path):
    if path == f"/{nonce}/webgl1-diagnostic.html":
        return 200,"text/html; charset=utf-8",page
    return 404,"text/plain",b"not found"


def normalize_state(state, nonce):
    """Keep only known, bounded diagnostic fields from the fixed fixture."""
    normalized={"nonce":nonce,"diagnostic_only":False,"state_valid":False,"context_ok":False,
                "context_lost":False,"stopped":False,"stages":[],"error":None,
                "gl_version":None,"glsl_version":None,"diagnostic_complete":False}
    if (not isinstance(state,dict) or state.get("nonce")!=nonce or
            state.get("diagnostic_only") is not True):
        normalized["error"]="invalid-state"
        return normalized
    normalized["diagnostic_only"]=True
    normalized["state_valid"]=True
    normalized["context_ok"]=state.get("context_ok") is True
    normalized["context_lost"]=state.get("context_lost") is True
    normalized["stopped"]=state.get("stopped") is True
    normalized["error"]=(state.get("error")[:64] if isinstance(state.get("error"),str) else None)
    for name in ("gl_version","glsl_version"):
        value=state.get(name)
        normalized[name]=value[:512] if isinstance(value,str) else None
    for name in ("context_attributes","single_sample_context_attributes"):
        attributes=state.get(name)
        keys=("alpha","antialias","depth","stencil","premultipliedAlpha",
              "preserveDrawingBuffer")
        normalized[name]=({key:attributes[key] for key in keys
                           if isinstance(attributes.get(key),bool)}
                          if isinstance(attributes,dict) else None)
    for name in ("sample_buffers","samples","single_sample_buffers","single_sample_count"):
        value=state.get(name)
        normalized[name]=(value if isinstance(value,int) and not isinstance(value,bool)
                          and 0<=value<=1024 else None)
    known=set(STAGE_NAMES)
    metadata_complete=True
    stages=state.get("stages")
    if isinstance(stages,list):
        for raw in stages[:MAX_STAGE_COUNT]:
            if not isinstance(raw,dict) or not isinstance(raw.get("name"),str) or raw.get("name") not in known:
                continue
            stage={"name":raw["name"],"status":raw.get("status") if raw.get("status") in
                   ("passed","failed","skipped") else "failed","checks":{},
                   "gl_errors":[],"prior_gl_errors":[],"pixel":None,
                   "expected_pixel":None,"details":{}}
            checks=raw.get("checks")
            if isinstance(checks,dict):
                stage["checks"]={key[:64]:value for key,value in list(checks.items())[:32]
                                  if isinstance(key,str) and isinstance(value,bool)}
            for key in ("gl_errors","prior_gl_errors"):
                values=raw.get(key)
                if isinstance(values,list):
                    stage[key]=[{"code":item.get("code"),
                                 "name":(item.get("name")[:64]
                                         if isinstance(item.get("name"),str) else "")}
                                for item in values[:MAX_GL_ERRORS_PER_STAGE]
                                if isinstance(item,dict) and isinstance(item.get("code"),int)
                                and not isinstance(item.get("code"),bool)
                                and -(2**31)<=item.get("code")<=2**31-1]
            for key in ("pixel","expected_pixel","clear_pixel","expected_clear_pixel",
                        "before_finish_pixel","after_finish_pixel"):
                value=raw.get(key)
                if isinstance(value,list) and len(value)==4 and all(
                        isinstance(channel,int) and not isinstance(channel,bool)
                        and 0<=channel<=255 for channel in value):
                    stage[key]=value
            details=raw.get("details")
            if isinstance(details,dict):
                for key,value in list(details.items())[:32]:
                    if not isinstance(key,str):
                        continue
                    if isinstance(value,bool):
                        stage["details"][key[:64]]=value
                    elif (isinstance(value,int) and not isinstance(value,bool)
                          and -(2**31)<=value<=2**31-1):
                        stage["details"][key[:64]]=value
                    elif isinstance(value,str):
                        stage["details"][key[:64]]=value[:MAX_SHADER_LOG]
                    elif isinstance(value,dict) and key in ("vertex_shader","fragment_shader","program"):
                        sub={}
                        for subkey,subvalue in list(value.items())[:4]:
                            if isinstance(subkey,str) and isinstance(subvalue,bool):
                                sub[subkey[:64]]=subvalue
                            elif (isinstance(subkey,str) and isinstance(subvalue,int)
                                  and not isinstance(subvalue,bool)
                                  and -(2**31)<=subvalue<=2**31-1):
                                sub[subkey[:64]]=subvalue
                            elif isinstance(subkey,str) and isinstance(subvalue,str):
                                sub[subkey[:64]]=subvalue[:MAX_SHADER_LOG]
                        stage["details"][key]=sub
                    elif isinstance(value,dict) and key=="draw_parameters":
                        allowed={"mode","first","count"}
                        mode=value.get("mode")
                        first=value.get("first")
                        count=value.get("count")
                        if (set(value)==allowed and
                            (mode is None and first is None and count is None or
                             mode in ("POINTS","TRIANGLES") and
                             isinstance(first,int) and not isinstance(first,bool) and
                             0<=first<=MAX_DRAW_VERTEX_COUNT and
                             isinstance(count,int) and not isinstance(count,bool) and
                             0<=count<=MAX_DRAW_VERTEX_COUNT)):
                            stage["details"][key]={"mode":mode,"first":first,"count":count}
                    elif value is None and key=="raster_state":
                        stage["details"][key]=None
                    elif isinstance(value,dict) and key=="raster_state":
                        bool_keys=("scissor_enabled","cull_enabled","depth_enabled",
                                   "depth_write_mask","stencil_enabled","blend_enabled")
                        valid_enums={"front_face":{0x0900,0x0901},
                                     "cull_mode":{0x0404,0x0405,0x0408},
                                     "depth_func":set(range(0x0200,0x0208))}
                        enum_keys=tuple(valid_enums)
                        vector_keys=("viewport","scissor_box")
                        expected=set(bool_keys+enum_keys+vector_keys+("sample_buffers","samples"))
                        valid=set(value)==expected and all(type(value.get(k)) is bool for k in bool_keys)
                        valid=valid and all(type(value.get(k)) is int and value[k] in choices
                            for k,choices in valid_enums.items())
                        for vector_key in vector_keys:
                            vector=value.get(vector_key)
                            valid=valid and isinstance(vector,list) and len(vector)==4 and all(
                                isinstance(item,int) and not isinstance(item,bool) and
                                -MAX_RASTER_COORDINATE<=item<=MAX_RASTER_COORDINATE for item in vector)
                        for sample_key in ("sample_buffers","samples"):
                            sample_value=value.get(sample_key)
                            valid=valid and isinstance(sample_value,int) and not isinstance(sample_value,bool) and 0<=sample_value<=1024
                        if valid:
                            stage["details"][key]={name:(list(value[name]) if name in vector_keys else value[name])
                                for name in expected}
                    elif isinstance(value,dict) and key=="attribute_state":
                        safe_state={}
                        for subkey,subvalue in list(value.items())[:8]:
                            if not isinstance(subkey,str):
                                continue
                            if subkey in ("enabled","normalized","buffer_binding_matches"):
                                if isinstance(subvalue,bool):
                                    safe_state[subkey]=subvalue
                            elif (subkey in ("size","type","stride","offset") and
                                  isinstance(subvalue,int) and not isinstance(subvalue,bool) and
                                  -(2**31)<=subvalue<=2**31-1):
                                safe_state[subkey]=subvalue
                        stage["details"][key]=safe_state
                    elif isinstance(value,list) and key=="current_attribute" and len(value)==4:
                        def safe_component(item):
                            if isinstance(item,bool) or not isinstance(item,(int,float)):
                                return False
                            if isinstance(item,int):
                                return abs(item)<=2**31
                            return math.isfinite(item) and abs(item)<=2**31
                        if all(safe_component(item) for item in value):
                            stage["details"][key]=value
            metadata_complete=metadata_complete and "draw_parameters" in stage["details"] and \
                "raster_state" in stage["details"]
            normalized["stages"].append(stage)
    raw_order=(isinstance(stages,list) and len(stages)==MAX_STAGE_COUNT and
        all(isinstance(item,dict) and isinstance(item.get("name"),str)
            for item in stages) and
        [item.get("name") for item in stages]==list(STAGE_NAMES))
    normalized["diagnostic_complete"]=(normalized["state_valid"] and raw_order
        and state.get("diagnostic_complete") is True
        and normalized["context_ok"] and not normalized["context_lost"]
        and not normalized["stopped"] and normalized["error"] is None
        and metadata_complete and len(normalized["stages"])==MAX_STAGE_COUNT
        and [item["name"] for item in normalized["stages"]]==list(STAGE_NAMES))
    normalized["completed_stage_count"]=len(normalized["stages"])
    normalized["stage_count"]=MAX_STAGE_COUNT
    return normalized


def fixture_url_is_valid(actual_url, expected_url, nonce):
    try:
        parsed=urllib.parse.urlsplit(actual_url)
        expected=urllib.parse.urlsplit(expected_url)
        return (actual_url==expected_url and parsed.scheme=="http" and
            parsed.hostname=="127.0.0.1" and parsed.port is not None and
            1<=parsed.port<=65535 and parsed.username is None and parsed.password is None and
            parsed.path==f"/{nonce}/webgl1-diagnostic.html" and not parsed.query and
            not parsed.fragment and expected.hostname=="127.0.0.1" and
            expected.scheme=="http" and expected.port is not None)
    except (TypeError,ValueError):
        return False


def read_state(cdp, nonce, expected_url):
    expression = """(() => {const s=window.__phase5_webgl1_diagnostic||{};return {url:location.href,title:document.title,body:document.body&&document.body.innerText,js_marker:document.getElementById('js-marker')&&document.getElementById('js-marker').textContent,state:s};})()"""
    response=cdp.call("Runtime.evaluate",{"expression":expression,"returnByValue":True},timeout=5)
    value=response.get("result",{}).get("value") or {}
    if not isinstance(value,dict):
        value={}
    url_ok=fixture_url_is_valid(value.get("url"),expected_url,nonce)
    body=value.get("body") if isinstance(value.get("body"),str) else ""
    return {"document_ok":url_ok and value.get("title")==f"PHASE5_WEBGL1_DIAGNOSTIC_{nonce}"
            and f"WEBGL1_DIAGNOSTIC_BODY_{nonce}" in body,
            "url_ok":url_ok,
            "js_marker":value.get("js_marker"),"state":normalize_state(value.get("state"),nonce)}


def diagnostic_state_ready(snapshot, nonce):
    """Wait for the fixture's terminal marker, not its provisional empty state."""
    if not isinstance(snapshot,dict):
        return False
    marker=snapshot.get("js_marker")
    return marker in (f"WEBGL1_DIAGNOSTIC_COMPLETE_{nonce}",
                      f"WEBGL1_DIAGNOSTIC_INCOMPLETE_{nonce}",
                      f"WEBGL1_DIAGNOSTIC_ERROR_{nonce}")


def diagnostic_classification(state, nonce, document_ok=False, main_hash_unchanged=True):
    """Every outcome remains diagnostic; stage success is never acceptance."""
    if (main_hash_unchanged is True and document_ok is True and
            isinstance(state,dict) and state.get("nonce")==nonce
            and state.get("diagnostic_only") is True and state.get("state_valid") is True):
        return "WEBGL1_DIAGNOSTIC_CAPTURED_REVIEW_PENDING"
    return "WEBGL1_DIAGNOSTIC_CAPTURE_INCOMPLETE"


def run(args):
    validate_options(args.startup_timeout,args.navigation_timeout,args.observe_seconds)
    output=Path(args.out).expanduser().absolute()
    if output.exists():
        raise FileExistsError("output directory already exists; choose a new diagnostic directory")
    requested_profile=validate_profile_dir(getattr(args,"profile_dir",None),output)
    context=probe.mac_context()
    app,executable,info=probe.app_executable(args.app)
    if info.get("CFBundleIdentifier")!="org.chromium.Chromium":
        raise RuntimeError("WebGL diagnostic runner accepts only an org.chromium.Chromium bundle")
    verified=subprocess.run(["/usr/bin/codesign","--verify","--deep","--strict","--verbose=4",str(app)],
        capture_output=True,text=True,timeout=60)
    if verified.returncode!=0:
        raise RuntimeError("strict deep codesign verification failed before browser launch")
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    profile=requested_profile or output/"profile"
    if requested_profile is None:
        profile.mkdir(mode=0o700)
    nonce=uuid.uuid4().hex; launch=family1_launch_configuration(executable,profile)
    main_hash_before=probe.sha256(executable)
    context_record={"context":context,"app":str(app),"bundle_identifier":info.get("CFBundleIdentifier"),
        "version":info.get("CFBundleShortVersionString"),"main_hash_before":main_hash_before,
        "codesign_strict_deep_verified":True,"nonce":nonce,"profile":str(profile),
        "browser_arguments":list(FAMILY1_ARGUMENTS),"browser_argv":launch["argv"],
        "runtime_environment":launch["runtime_environment"],
        "startup_timeout_seconds":args.startup_timeout,"navigation_timeout_seconds":args.navigation_timeout,
        "observe_seconds":args.observe_seconds,"raw_netlog_enabled":False,"diagnostic_only":True,
        "profile_reused":requested_profile is not None,
        "acceptance_runner_unchanged":"webgl1_runner.py","gui_confirmation_required":True,
        "same_gpu_pid_library_review_required":True}
    probe.write_json(output/"context.json",context_record); probe.write_json(output/"launch.json",launch)
    server=DiagnosticFixtureServer(nonce,diagnostic_page(nonce))
    thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
    url=f"http://127.0.0.1:{server.server_port}/{nonce}/webgl1-diagnostic.html"
    result={"classification":"WEBGL1_DIAGNOSTIC_CAPTURE_INCOMPLETE","diagnostic_only":True,
        "nonce":nonce,"url":url,"pid":None,"started_at":timestamp(),"navigated":False,
        "state_observed_at":None,"gui_observation_started_at":None,"gui_observation_finished_at":None,
        "diagnostic_state":None,"diagnostic_state_valid":False,"errors":[]}
    process=cdp=None
    process_environment=os.environ.copy(); process_environment.pop(OPT_IN_ENV,None); process_environment[OPT_IN_ENV]="1"
    try:
        with (output/"browser-stdout.log").open("wb") as stdout, \
             (output/"browser-stderr.log").open("wb") as stderr, \
             (output/"cdp-events.jsonl").open("w",encoding="utf-8") as events:
            try:
                process=subprocess.Popen(launch["argv"],stdout=stdout,stderr=stderr,
                    start_new_session=True,env=process_environment)
                result["pid"]=process.pid
                target=probe.wait_for_page_target(profile,process,args.startup_timeout)
                cdp=probe.CDP(target["webSocketDebuggerUrl"],events)
                gpu_info=accepted_runner.capture_browser_gpu_info(profile,process.pid)
                probe.write_json(output/"gpu-info.json",gpu_info)
                result["gpu_info_diagnostic"]={"file":"gpu-info.json","status":gpu_info["status"],
                    "observed_at":gpu_info["observed_at"],"browser_pid":gpu_info["browser_pid"]}
                for method in ("Page.enable","Network.enable","Runtime.enable"):
                    cdp.call(method)
                cdp.call("Page.navigate",{"url":url},timeout=args.navigation_timeout)
                result["navigated"]=True
                deadline=time.monotonic()+accepted_runner.STATE_WAIT_SECONDS
                snapshot={}
                while time.monotonic()<deadline:
                    try:
                        snapshot=read_state(cdp,nonce,url)
                        if diagnostic_state_ready(snapshot,nonce):
                            result["state_observed_at"]=timestamp(); break
                    except Exception as exc:
                        result["errors"].append(f"runtime-evaluate:{type(exc).__name__}")
                    time.sleep(0.2)
                result["document_ok"]=snapshot.get("document_ok",False)
                result["url_ok"]=snapshot.get("url_ok",False)
                result["js_marker"]=snapshot.get("js_marker")
                result["diagnostic_state"]=snapshot.get("state")
                result["diagnostic_state_valid"]=(result["document_ok"] and
                    isinstance(result["diagnostic_state"],dict) and
                    result["diagnostic_state"].get("nonce")==nonce and
                    result["diagnostic_state"].get("state_valid") is True and
                    result["diagnostic_state"].get("diagnostic_only") is True)
                result["http_document_200"]=any(event.get("method")=="Network.responseReceived"
                    and event.get("type")=="Document" and event.get("status")==200 for event in cdp.events)
                try:
                    image=cdp.call("Page.captureScreenshot",{"format":"png"},timeout=5)
                    (output/"diagnostic-page.png").write_bytes(base64.b64decode(image["data"]))
                except Exception as exc:
                    result["errors"].append(f"screenshot:{type(exc).__name__}")
                if args.observe_seconds:
                    result["gui_observation_started_at"]=timestamp()
                    print(f"Observe the diagnostic page and stage list for {args.observe_seconds} seconds.",flush=True)
                    time.sleep(args.observe_seconds)
                    result["gui_observation_finished_at"]=timestamp()
            except Exception as exc:
                result["errors"].append(f"{type(exc).__name__}:{str(exc)[:300]}")
            finally:
                if cdp:
                    try: cdp.call("Browser.close",timeout=2)
                    except Exception: pass
                    try: cdp.ws.close()
                    except Exception: pass
                if process:
                    try: process.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        result["errors"].append("browser did not exit after Browser.close; process left running")
                    result["returncode"]=process.returncode
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=2)
    result["finished_at"]=timestamp(); result["server_events"]=list(server.events)
    result["server_events_truncated"]=server.events_truncated
    result["main_hash_after"]=probe.sha256(executable)
    result["main_hash_unchanged"]=result["main_hash_after"]==main_hash_before
    if not result["main_hash_unchanged"]:
        result["errors"].append("main-executable-hash-changed")
    result["classification"]=diagnostic_classification(result.get("diagnostic_state"),nonce,
        result.get("document_ok") is True,result.get("main_hash_unchanged") is True)
    probe.write_json(output/"result.json",result)
    print(result["classification"]); print(f"Diagnostic evidence: {output}")
    return 0 if (result["diagnostic_state_valid"] and result.get("document_ok") is True and
                 result.get("main_hash_unchanged") is True and
                 result.get("returncode")==0) else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app",required=True)
    parser.add_argument("--out",required=True,help="New diagnostic directory; existing directories are refused")
    parser.add_argument("--profile-dir",help="Reuse an existing dedicated test profile without creating a profile")
    parser.add_argument("--startup-timeout",type=int,default=45)
    parser.add_argument("--navigation-timeout",type=int,default=60)
    parser.add_argument("--observe-seconds",type=int,default=20)
    args=parser.parse_args()
    try: validate_options(args.startup_timeout,args.navigation_timeout,args.observe_seconds)
    except ValueError as exc: parser.error(str(exc))
    try: return run(args)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}",file=sys.stderr); return 1


if __name__=="__main__":
    sys.exit(main())
