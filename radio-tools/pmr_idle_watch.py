#!/usr/bin/env python3
"""Run the PMR scanner after Nginx has been idle, and stop it on new visitors."""

import logging
import grp
import os
from pathlib import Path
import socket
import subprocess
import time
import sys
sys.path.insert(0, "/home/user/radio-tools")
from meteo import due as meteo_due


ACCESS_LOG = Path("/var/log/nginx/access.log")
IDLE_SECONDS = 2 * 60
POLL_SECONDS = 1
SCAN_UNIT = "pmr-scan.service"
SCAN_ENABLED = False  # Meteor LRPT is the only unattended recording task.
WEB_PORTS = {80, 443, 8073}
RETRY_SECONDS = 30
LOG = logging.getLogger("pmr-idle-watch")
CONTROL_SOCKET = "/run/pmr-idle-watch/control.sock"


def control_listener():
    Path(CONTROL_SOCKET).unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(CONTROL_SOCKET)
    os.chown(CONTROL_SOCKET, 0, grp.getgrnam("openwebrx").gr_gid)
    os.chmod(CONTROL_SOCKET, 0o660)
    server.listen(8)
    server.settimeout(POLL_SECONDS)
    return server


def release_for_web(server):
    """Acknowledge only after systemd has released the scanner's whole cgroup."""
    try:
        connection, _ = server.accept()
    except socket.timeout:
        return False
    with connection:
        connection.settimeout(2)
        try:
            set_meteo(False)
            set_scanner(False)
            reset_tuner_for_web()
            connection.sendall(b"OK\n")
        except (OSError, subprocess.SubprocessError):
            LOG.exception("Tuner handover failed")
    return True


def reset_tuner_for_web():
    """Recover the known Blog V4 before handing it to a new connector."""
    if connector_running():
        # Never reset a receiver already owned by another OpenWebRX source.
        raise OSError("Another rtl_connector is still running; refusing USB reset")
    devices = []
    for device in Path("/sys/bus/usb/devices").iterdir():
        try:
            if ((device / "idVendor").read_text().strip() == "0bda"
                    and (device / "idProduct").read_text().strip() == "2838"
                    and (device / "serial").read_text().strip() == "REDACTED_DEVICE_SERIAL"):
                devices.append(device)
        except FileNotFoundError:
            continue
    if len(devices) != 1:
        raise OSError("Expected exactly one RTL-SDR Blog V4 with serial REDACTED_DEVICE_SERIAL")
    device = devices[0]
    address = (f"{int((device / 'busnum').read_text()):03d}/"
               f"{int((device / 'devnum').read_text()):03d}")
    LOG.info("Resetting idle RTL-SDR %s before receiver start", address)
    subprocess.run(["/usr/bin/usbreset", address], check=True, timeout=5)


def connector_running():
    # Also protect background OpenWebRX receivers with no browser attached.
    for entry in Path("/proc").glob("[0-9]*/exe"):
        try:
            # The Python handover wrapper also has comm=rtl_connector.
            # Only the native binary owns the USB device.
            if os.readlink(entry) == "/usr/bin/rtl_connector":
                return True
        except (FileNotFoundError, ProcessLookupError):
            pass
    return False


def web_connections():
    """Count established connections to nginx or OpenWebRX directly."""
    count = 0
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table, encoding="ascii") as source:
                next(source, None)
                for line in source:
                    fields = line.split()
                    if len(fields) < 4 or fields[3] != "01":  # TCP_ESTABLISHED
                        continue
                    try:
                        port = int(fields[1].rsplit(":", 1)[1], 16)
                    except (IndexError, ValueError):
                        continue
                    if port in WEB_PORTS:
                        count += 1
        except FileNotFoundError:
            continue
    return count


def scanner_active():
    return subprocess.run(
        ["/usr/bin/systemctl", "is-active", "--quiet", SCAN_UNIT],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=10,
    ).returncode == 0


def set_scanner(active):
    if active:
        # A failed scanner may have left USB streaming wedged. No receiver
        # owns the device at this point; a reset makes retries meaningful.
        reset_tuner_for_web()
    action = "start" if active else "stop"
    LOG.info("%s %s", action.capitalize(), SCAN_UNIT)
    result = subprocess.run(
        ["/usr/bin/systemctl", action, SCAN_UNIT],
        check=False,
        timeout=20,
    )
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, result.args)


def meteo_active():
    return subprocess.run(['systemctl', 'is-active', '--quiet', 'meteo-capture'],
                          timeout=10).returncode == 0


def set_meteo(active):
    subprocess.run(['systemctl', 'start' if active else 'stop', 'meteo-capture'],
                   check=True, timeout=20)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    try:
        last_log_change = ACCESS_LOG.stat().st_mtime_ns
    except OSError:
        LOG.exception("Cannot read Nginx access log %s", ACCESS_LOG)
        raise SystemExit(1)

    last_activity = time.monotonic()
    # Start a fresh idle interval: old log timestamps cannot prove that no
    # WebSocket client was connected before this watcher started.
    next_start = 0.0
    server = control_listener()
    LOG.info("Watching %s; idle threshold is %d seconds", ACCESS_LOG, IDLE_SECONDS)

    while True:
        try:
            if release_for_web(server):
                last_activity = time.monotonic()
            current_log_change = ACCESS_LOG.stat().st_mtime_ns
            if current_log_change != last_log_change:
                last_log_change = current_log_change
                last_activity = time.monotonic()

            connections = web_connections()
            active = scanner_active()

            if connections or connector_running():
                # This catches open WebSocket/TLS sessions even though Nginx only
                # writes their access-log entry when the connection closes.
                last_activity = time.monotonic()
                if meteo_active():
                    set_meteo(False)
                if active:
                    LOG.info("Web connection detected; returning the tuner to OpenWebRX")
                    set_scanner(False)
            elif meteo_due() and time.monotonic() - last_activity >= IDLE_SECONDS:
                if not meteo_active() and time.monotonic() >= next_start:
                    next_start = time.monotonic() + RETRY_SECONDS
                    set_scanner(False)
                    reset_tuner_for_web()
                    set_meteo(True)
            elif meteo_active():
                set_meteo(False)
            elif active and time.monotonic() - last_activity < IDLE_SECONDS:
                set_scanner(False)
            elif (not active and SCAN_ENABLED and time.monotonic() - last_activity >= IDLE_SECONDS
                  and time.monotonic() >= next_start):
                next_start = time.monotonic() + RETRY_SECONDS
                set_scanner(True)

        except (OSError, subprocess.SubprocessError):
            LOG.exception("Watcher iteration failed")
            last_activity = time.monotonic()
            # If activity cannot be checked, release the receiver.
            try:
                set_meteo(False)
                set_scanner(False)
            except (OSError, subprocess.SubprocessError):
                LOG.exception("Could not stop scanner after watcher failure")
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
