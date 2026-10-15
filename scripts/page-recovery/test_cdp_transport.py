from __future__ import annotations

import socket
import json
import time
import unittest
from unittest import mock

import cdp_transport


class FakeSocket:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = list(chunks)
        self.sent: list[bytes] = []
        self.closed = False
        self.timeout = None

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def sendall(self, value: bytes) -> None:
        self.sent.append(value)

    def recv(self, _size: int) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        raise socket.timeout()

    def close(self) -> None:
        self.closed = True


def frame(opcode: int, payload: bytes, *, final: bool = True) -> bytes:
    assert len(payload) < 126
    return bytes([(0x80 if final else 0) | opcode, len(payload)]) + payload


def client(ws: cdp_transport.WebSocket, sock: FakeSocket) -> None:
    ws.sock = sock
    ws.event_log = None
    ws._recv_buffer = bytearray()
    ws._frame_state = None
    ws._fragments = []
    ws._fragment_opcode = None
    ws._fragment_bytes = 0


class WebSocketTimeoutResumeTests(unittest.TestCase):
    def test_partial_header_resume(self) -> None:
        sock = FakeSocket([b'\x81'])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        sock.chunks.extend([b'\x0b', b'{"ok":true}'])
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"ok": True})

    def test_partial_payload_resume(self) -> None:
        sock = FakeSocket([b'\x81\x0b', b'{"'])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        sock.chunks.append(b'ok":true}')
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"ok": True})

    def test_extended_length_and_mask_resume(self) -> None:
        payload = json.dumps({"text": "x" * 120}, separators=(",", ":")).encode()
        self.assertGreaterEqual(len(payload), 126)
        header = bytes([0x81, 126]) + len(payload).to_bytes(2, "big")
        sock = FakeSocket([header[:3]])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        sock.chunks.append(header[3:] + payload)
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"text": "x" * 120})

        key = b"mask"
        masked = bytes(byte ^ key[index % 4] for index, byte in enumerate(b'{"masked":true}'))
        sock = FakeSocket([b'\x81\x8f', key[:2]])
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        sock.chunks.extend([key[2:] + masked[:4], masked[4:]])
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"masked": True})

    def test_multiple_buffered_messages_and_close(self) -> None:
        first = frame(1, b'{"first":1}')
        second = frame(1, b'{"second":2}')
        sock = FakeSocket([first + second])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"first": 1})
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"second": 2})
        sock.chunks.append(frame(8, b""))
        with self.assertRaisesRegex(RuntimeError, "sent close"):
            ws.recv_message(time.monotonic() + 1)

    def test_fragment_continuation_resumes_after_timeout(self) -> None:
        encoded = b'{"resumed":true}'
        split = 7
        sock = FakeSocket([frame(1, encoded[:split], final=False), b'\x80'])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        sock.chunks.append(bytes([len(encoded) - split]) + encoded[split:])
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"resumed": True})

    def test_ping_interleaved_with_fragmented_text_is_answered(self) -> None:
        encoded = b'{"pong":true}'
        split = 5
        sock = FakeSocket([frame(1, encoded[:split], final=False), frame(9, b"p"),
                           frame(0, encoded[split:])])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        self.assertEqual(ws.recv_message(time.monotonic() + 1), {"pong": True})
        self.assertEqual(len(sock.sent), 1)
        self.assertEqual(sock.sent[0][0] & 0x0F, 10)

    def test_buffered_pings_still_observe_deadline(self) -> None:
        buffered = frame(9, b"1") + frame(9, b"2")
        sock = FakeSocket([])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        ws._recv_buffer.extend(buffered)
        with mock.patch.object(cdp_transport.time, "monotonic", side_effect=[0.0, 2.0]):
            with self.assertRaises(TimeoutError):
                ws.recv_message(1.0)
        self.assertEqual(sock.sent[0][0] & 0x0F, 10)
        self.assertEqual(len(ws._recv_buffer), len(frame(9, b"2")))

    def test_fragment_aggregate_limit(self) -> None:
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        sock = FakeSocket([frame(1, b"1234567", final=False), frame(0, b"8901")])
        client(ws, sock)
        with mock.patch.object(cdp_transport, "MAX_WEBSOCKET_MESSAGE_BYTES", 10):
            with self.assertRaisesRegex(RuntimeError, "message exceeds size limit"):
                ws.recv_message(time.monotonic() + 1)

    def test_read_timeout_restored_after_deadline(self) -> None:
        sock = FakeSocket([b"\x81"])
        ws = cdp_transport.WebSocket.__new__(cdp_transport.WebSocket)
        client(ws, sock)
        with self.assertRaises(TimeoutError):
            ws.recv_message(time.monotonic() + 0.01)
        self.assertEqual(sock.timeout, 0.5)


    def test_handshake_keeps_trailing_frame_bytes(self) -> None:
        message = {"upgrade": "ready"}
        trailer = frame(1, json.dumps(message).encode())
        sock = FakeSocket([b"HTTP/1.1 101 Switching Protocols\r\n\r\n" + trailer])
        with mock.patch.object(cdp_transport.socket, "create_connection", return_value=sock):
            ws = cdp_transport.WebSocket("ws://127.0.0.1/devtools", None)
        self.assertEqual(ws.recv_message(time.monotonic() + 1), message)


if __name__ == "__main__":
    unittest.main()
