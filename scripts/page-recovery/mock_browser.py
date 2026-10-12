#!/usr/bin/env python3
"""Test-only CDP peer; never a browser or a rendering test."""
import base64
import hashlib
import http.server
import json
from pathlib import Path
import re
import struct
import sys
import threading
import urllib.parse

from probe import OPENER
from test_kit import png

options = dict(arg[2:].split("=",1) for arg in sys.argv[1:] if arg.startswith("--") and "=" in arg)
profile = Path(options["user-data-dir"])
no_http = "--simulate-http-blocked" in sys.argv


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def frame(self, value):
        data = json.dumps(value).encode()
        if len(data) < 126:
            header = bytes((0x81,len(data)))
        elif len(data) < 65536:
            header = bytes((0x81,126)) + struct.pack(">H",len(data))
        else:
            header = bytes((0x81,127)) + struct.pack(">Q",len(data))
        self.wfile.write(header+data)
        self.wfile.flush()

    def message(self):
        header = self.rfile.read(2)
        if len(header) != 2:
            raise EOFError()
        length = header[1]&127
        if length == 126: length = struct.unpack(">H",self.rfile.read(2))[0]
        elif length == 127: length = struct.unpack(">Q",self.rfile.read(8))[0]
        mask = self.rfile.read(4) if header[1]&128 else b""
        data = self.rfile.read(length)
        if mask: data = bytes(v^mask[i%4] for i,v in enumerate(data))
        return json.loads(data)

    def do_GET(self):
        if self.path == "/json/list":
            body = json.dumps([{"type":"page","webSocketDebuggerUrl":f"ws://127.0.0.1:{self.server.server_port}/devtools/page/mock"}]).encode()
            self.send_response(200)
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(101)
        self.send_header("Upgrade","websocket")
        self.send_header("Connection","Upgrade")
        self.send_header("Sec-WebSocket-Accept",base64.b64encode(hashlib.sha1((self.headers["Sec-WebSocket-Key"]+"258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode())
        self.end_headers()
        self.wfile.flush()
        url,nonce = "about:blank",None
        while True:
            message = self.message()
            method,params = message["method"],message.get("params",{})
            value = {}
            if method == "Page.navigate":
                requested = params["url"]
                if not (no_http and requested.startswith("http:")):
                    url = requested
                    if url.startswith("data:"):
                        page = base64.b64decode(url.split(",",1)[1]).decode()
                    elif url.startswith("file:"):
                        page = Path(urllib.parse.unquote(urllib.parse.urlsplit(url).path)).read_text()
                    else:
                        with OPENER.open(url,timeout=2) as response: page = response.read().decode()
                        self.frame({"method":"Network.responseReceived","params":{"requestId":"mock-document","type":"Document","response":{"status":200}}})
                    nonce = re.search(r"PAGE_RECOVERY_([0-9a-f]{32})",page).group(1)
            elif method == "Runtime.evaluate":
                document = {"url":url,"title":"","body":"","probe":None,"rect":None}
                if nonce:
                    document.update({"title":"PAGE_RECOVERY_"+nonce,"body":"BODY_OK_"+nonce,
                                     "probe":{"nonce":nonce,"js_ok":True,"canvas_ok":True,"fetch_ok":True},
                                     "rect":{"x":16,"y":64,"width":96,"height":96}})
                value = {"result":{"type":"object","value":document}}
            elif method == "Page.captureScreenshot":
                value = {"data":base64.b64encode(png((0,160,0) if nonce else (255,255,255))).decode()}
            self.frame({"id":message["id"],"result":value})
            if method == "Browser.close":
                threading.Thread(target=self.server.shutdown,daemon=True).start()
                return


server = http.server.ThreadingHTTPServer(("127.0.0.1",0),Handler)
server.daemon_threads = True
(profile / "DevToolsActivePort").write_text(str(server.server_port)+"\n/devtools/browser/mock\n")
server.serve_forever()
server.server_close()
