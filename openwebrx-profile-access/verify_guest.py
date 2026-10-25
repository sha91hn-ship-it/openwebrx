"""Check the public receiver WebSocket without logging in."""

import base64
import json
import os
import socket
import struct
import time


def read_exact(sock, count):
    result = b""
    while len(result) < count:
        chunk = sock.recv(count - len(result))
        if not chunk:
            raise EOFError("WebSocket closed")
        result += chunk
    return result


def receive(sock):
    head = read_exact(sock, 2)
    length = head[1] & 127
    if length == 126:
        length = struct.unpack("!H", read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(sock, 8))[0]
    mask = read_exact(sock, 4) if head[1] & 128 else None
    data = read_exact(sock, length)
    if mask:
        data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
    return head[0] & 15, data


def send_text(sock, message):
    data = message.encode()
    mask = os.urandom(4)
    length = len(data)
    if length <= 125:
        header = bytes([0x81, 0x80 | length])
    elif length <= 65535:
        header = bytes([0x81, 0x80 | 126]) + struct.pack("!H", length)
    else:
        header = bytes([0x81, 0x80 | 127]) + struct.pack("!Q", length)
    sock.sendall(header + mask + bytes(byte ^ mask[index % 4] for index, byte in enumerate(data)))


def main():
    with socket.create_connection(("127.0.0.1", 8073), timeout=10) as sock:
        sock.settimeout(10)
        key = base64.b64encode(os.urandom(16)).decode()
        request = (
            "GET /ws/ HTTP/1.1\r\n"
            "Host: 127.0.0.1:8073\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(request.encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += sock.recv(1)
        assert b"101 Switching Protocols" in response, response
        send_text(sock, "SERVER DE CLIENT type=receiver")
        deadline = time.monotonic() + 20
        profile_message = None
        while time.monotonic() < deadline:
            opcode, data = receive(sock)
            if opcode != 1:
                continue
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            if message.get("type") == "profiles":
                profile_message = message
                break
        assert profile_message is not None, "No profile list"
        profiles = profile_message["value"]
        protected = [profile for profile in profiles if profile["id"].startswith(("rtlsdr|fm_", "rtlsdr|airband_"))]
        assert not protected, protected
        assert len(profiles) == 19, len(profiles)
        print("Guest WebSocket: 19 public profiles, 0 FM/airband profiles")

        send_text(sock, json.dumps({"type": "selectprofile", "params": {"profile": "rtlsdr|fm_88"}}))
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            opcode, data = receive(sock)
            if opcode != 1:
                continue
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                continue
            if "Login is required for this profile" in str(message):
                print("Guest profile selection: rejected")
                return
        raise AssertionError("No access rejection received")


if __name__ == "__main__":
    main()
