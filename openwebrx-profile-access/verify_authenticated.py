"""Temporarily log in to check protected profiles, then remove the test user."""

import base64
import http.cookiejar
import json
import os
import secrets
import socket
import time
import urllib.parse
import urllib.request

from owrx.users import DefaultPasswordClass, User, UserList
from owrx.config.core import CoreConfig
from verify_guest import read_exact, receive, send_text


def main():
    CoreConfig.load()
    username = "access_test_" + secrets.token_hex(5)
    password = secrets.token_urlsafe(24)
    users = UserList()
    users.addUser(User(username, True, DefaultPasswordClass(password)))
    try:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        form = urllib.parse.urlencode({"user": username, "password": password}).encode()
        opener.open("http://127.0.0.1:8073/login?ref=/", form, timeout=10).read()
        cookies = {cookie.name: cookie.value for cookie in jar}
        assert "owrx-session" in cookies, "No login session cookie"

        status = json.load(opener.open("http://127.0.0.1:8073/status.json", timeout=10))
        profiles = [profile for sdr in status["sdrs"] for profile in sdr["profiles"]]
        assert len(profiles) == 33, len(profiles)
        assert sum(p["name"].startswith(("FM ", "Airband")) for p in profiles) == 14
        print("Authenticated status: all 33 profiles visible")

        with socket.create_connection(("127.0.0.1", 8073), timeout=10) as sock:
            sock.settimeout(10)
            key = base64.b64encode(os.urandom(16)).decode()
            request = (
                "GET /ws/ HTTP/1.1\r\n"
                "Host: 127.0.0.1:8073\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Cookie: owrx-session={cookies['owrx-session']}\r\n"
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
            while time.monotonic() < deadline:
                opcode, data = receive(sock)
                if opcode != 1:
                    continue
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if message.get("type") == "profiles":
                    listed = message["value"]
                    assert len(listed) == 33, len(listed)
                    protected = [p for p in listed if p["id"].startswith(("rtlsdr|fm_", "rtlsdr|airband_"))]
                    assert len(protected) == 14, protected
                    print("Authenticated WebSocket: all 14 protected profiles visible")
                    return
            raise AssertionError("No authenticated profile list")
    finally:
        users.deleteUser(username)


if __name__ == "__main__":
    main()
