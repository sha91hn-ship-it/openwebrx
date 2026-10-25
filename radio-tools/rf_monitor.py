#!/usr/bin/env python3
"""RTL-SDR helpers for PMR446 activity clips and 430-440 MHz surveys.

Requires rtl_fm, rtl_power, rtl_433, and an RTL-SDR visible to this host.
"""

import argparse
import collections
import csv
import datetime as dt
import math
import os
import select
from pathlib import Path
import shutil
import signal
import subprocess
import time
import wave
from zoneinfo import ZoneInfo


SAMPLE_RATE = 24_000
CHANNELS = [446_006_250 + index * 12_500 for index in range(16)]
LOCATION_REPEATER_INPUT_HZ = int(os.environ.get("REPEATER_INPUT_HZ", "0"))
if LOCATION_REPEATER_INPUT_HZ:
    CHANNELS.append(LOCATION_REPEATER_INPUT_HZ)
DEFAULT_MAX_STORAGE_GB = 4.0
LOCATION_REPEATER_OUTPUT_HZ = int(os.environ.get("REPEATER_OUTPUT_HZ", "0"))
CB_USB = 27_385_000
LOCAL_TIMEZONE = ZoneInfo(os.environ.get("LOCAL_TIMEZONE", "UTC"))


def downlink_window_open(now=None):
    now = dt.datetime.now(LOCAL_TIMEZONE) if now is None else now.astimezone(LOCAL_TIMEZONE)
    minute = now.hour * 60 + now.minute
    return 450 <= minute < 480 or 1170 <= minute < 1200


def channel_enabled(frequency, now=None):
    return frequency != LOCATION_REPEATER_OUTPUT_HZ or downlink_window_open(now)


def scan_channels():
    return [*CHANNELS, *([LOCATION_REPEATER_OUTPUT_HZ] if LOCATION_REPEATER_OUTPUT_HZ else [])]


def receiver_settings(frequency, args):
    if frequency == CB_USB:
        return "usb", 6000, 0, args.cb_threshold
    squelch = args.squelch
    if frequency == LOCATION_REPEATER_INPUT_HZ and LOCATION_REPEATER_INPUT_HZ:
        squelch = args.repeater_squelch
    elif frequency == LOCATION_REPEATER_OUTPUT_HZ:
        squelch = args.downlink_squelch
    return "fm", SAMPLE_RATE, squelch, args.threshold


class AudioGate:
    def __init__(self, threshold, minimum_seconds):
        self.threshold = threshold
        self.minimum_seconds = minimum_seconds
        self.seconds = 0.0

    def reset(self):
        self.seconds = 0.0

    def update(self, level, duration, warmed_up):
        active = warmed_up and level >= self.threshold
        self.seconds = self.seconds + duration if active else 0.0
        return active, active and self.seconds >= self.minimum_seconds


def require_program(name):
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"Required program not found: {name}")
    return path


def stamp():
    return dt.datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")


def prepare_output_dir(value):
    path = Path(value).expanduser()
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def rotate_output_files(out_dir, limit_bytes, reserve_bytes):
    managed = []
    for pattern in ("pmr446_*.wav", "cb_usb_*.wav", "weather_spectrum_*.csv", "weather_decode_*.jsonl"):
        managed.extend(out_dir.glob(pattern))
    managed = [path for path in managed if path.is_file()]
    total_bytes = sum(path.stat().st_size for path in managed)
    for path in sorted(managed, key=lambda item: item.stat().st_mtime):
        if total_bytes + reserve_bytes <= limit_bytes:
            break
        try:
            size = path.stat().st_size
            path.unlink()
            total_bytes -= size
            print(f"Storage limit: removed oldest file {path.name}", flush=True)
        except FileNotFoundError:
            continue
    if total_bytes + reserve_bytes > limit_bytes:
        raise SystemExit(
            "The configured radio-file limit cannot reserve space for the next output. "
            "Remove unrelated files from the output directory or raise the limit."
        )


def sample_level_dbfs(pcm):
    count = len(pcm) // 2
    if not count:
        return -120.0
    values = memoryview(pcm[: count * 2]).cast("h")
    mean_square = sum(value * value for value in values) / count
    if mean_square <= 0:
        return -120.0
    return 10.0 * math.log10(mean_square / (32768.0 * 32768.0))


def check_pmr_input(rtl_fm, args):
    """A squelched channel cannot distinguish silence from a wedged USB tuner."""
    command = [rtl_fm, "-d", str(args.device), "-f", str(CHANNELS[0]),
               "-M", "fm", "-s", str(SAMPLE_RATE), "-l", "0", "-"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, bufsize=0)
    try:
        ready, _, _ = select.select([process.stdout], [], [], 5)
        if not ready or not os.read(process.stdout.fileno(), 4096):
            raise SystemExit("RTL-SDR input stalled: no unsquelched PCM in 5s; "
                             "exiting so the idle watcher can reset the tuner.")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        process.stdout.close()


def pmr_scan(args):
    rtl_fm = require_program("rtl_fm")
    out_dir = prepare_output_dir(args.output)

    print("PMR446 scan started (Ctrl+C to stop). One channel is monitored at a time.", flush=True)
    print("Channels: 446.00625–446.19375 MHz, 12.5 kHz spacing; "
          "plus 145.11250 MHz (REPEATER input).", flush=True)
    print("REPEATER output 145.71250 MHz: daily 07:30–08:00 and 19:30–20:00 "
          "UTC; squelch=" + str(args.downlink_squelch), flush=True)
    print("CB automatic recording disabled.", flush=True)
    # Let systemd stop the scanner cleanly so rtl_fm and any open WAV are closed
    # before OpenWebRX takes the RTL-SDR back.
    def stop_on_sigterm(signum, frame):
        raise KeyboardInterrupt

    previous_sigterm = signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        while True:
            check_pmr_input(rtl_fm, args)
            candidates = scan_channels()
            count = sum(channel_enabled(f) for f in candidates)
            print(f"RTL-SDR input OK; starting {count}-channel sweep.", flush=True)
            for index, frequency in enumerate(candidates, start=1):
                if not channel_enabled(frequency):
                    continue
                mode, sample_rate, squelch, threshold = receiver_settings(frequency, args)
                block_bytes = 1024 if mode == "usb" else 4096
                block_seconds = block_bytes / (sample_rate * 2)
                pre_roll = collections.deque(maxlen=max(1, math.ceil(
                    max(args.pre_roll, args.cb_open_seconds if mode == "usb" else 0)
                    / block_seconds)))
                command = [
                    rtl_fm,
                    "-d", str(args.device),
                    "-f", str(frequency),
                    "-M", mode,
                    "-s", str(sample_rate),
                    "-r", str(sample_rate),
                    "-l", str(squelch),
                    "-",
                ]
                if args.gain.lower() != "auto":
                    command[-1:-1] = ["-g", args.gain]
                process = subprocess.Popen(
                    command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    bufsize=0,
                )
                started = time.monotonic()
                # USB/tuner initialization can take longer than the channel
                # dwell. Wait for PCM before timing the actual observation.
                dwell_deadline = started + args.startup_timeout
                received_pcm = False
                clip = None
                clip_path = None
                clip_start = None
                clip_start_monotonic = None
                quiet_since = None
                recorded_seconds = 0.0
                warmup_until = started + args.warmup
                pending_pcm = b""
                gate = AudioGate(threshold, args.cb_open_seconds if mode == "usb" else 0.0)
                last_pcm = started
                try:
                    while True:
                        if not channel_enabled(frequency):
                            break
                        now = time.monotonic()
                        if clip is None and now >= dwell_deadline:
                            break
                        if clip is not None and now - clip_start_monotonic >= args.max_record:
                            break
                        # rtl_fm may stop emitting PCM while squelched. Poll so
                        # channel dwell and recording deadlines still apply.
                        ready, _, _ = select.select([process.stdout], [], [], 0.05)
                        if not ready:
                            if time.monotonic() - last_pcm > 0.25:
                                gate.reset()
                            if clip is not None:
                                if quiet_since is None:
                                    quiet_since = time.monotonic()
                                elif time.monotonic() - quiet_since >= args.hang:
                                    break
                            continue
                        pcm = os.read(process.stdout.fileno(), block_bytes)
                        if not pcm:
                            break
                        if not received_pcm:
                            received_pcm = True
                            warmup_until = time.monotonic() + args.warmup
                            dwell_deadline = warmup_until + args.dwell
                        pcm = pending_pcm + pcm
                        complete_bytes = len(pcm) & ~1
                        pending_pcm = pcm[complete_bytes:]
                        pcm = pcm[:complete_bytes]
                        if not pcm:
                            continue
                        last_pcm = time.monotonic()
                        level = sample_level_dbfs(pcm)
                        active, opened = gate.update(
                            level, len(pcm) / (sample_rate * 2),
                            time.monotonic() >= warmup_until)
                        if clip is None:
                            pre_roll.append(pcm)
                            if opened:
                                clip_start = dt.datetime.now().astimezone()
                                rotate_output_files(
                                    out_dir,
                                    int(args.max_storage_gb * 1_000_000_000),
                                    int((args.max_record + args.pre_roll
                                         + args.cb_open_seconds + 2 * block_seconds) * sample_rate * 2) + 44,
                                )
                                filename = (
                                    f"{'cb_usb' if mode == 'usb' else 'pmr446'}_"
                                    f"{clip_start.strftime('%Y%m%d_%H%M%S')}_"
                                    f"ch{index:02d}_{frequency / 1_000_000:.5f}MHz.wav"
                                )
                                clip_path = out_dir / filename
                                clip_start_monotonic = time.monotonic()
                                clip = wave.open(str(clip_path), "wb")
                                clip_path.chmod(0o600)
                                clip.setnchannels(1)
                                clip.setsampwidth(2)
                                clip.setframerate(sample_rate)
                                for old_pcm in pre_roll:
                                    clip.writeframesraw(old_pcm[: len(old_pcm) & ~1])
                                    recorded_seconds += len(old_pcm) / (sample_rate * 2)
                                pre_roll.clear()
                                print(
                                    f"Activity: CH{index:02d} {frequency / 1_000_000:.5f} MHz "
                                    f"({level:.1f} dBFS)", flush=True
                                )
                        else:
                            clip.writeframesraw(pcm[: len(pcm) & ~1])
                            recorded_seconds += len(pcm) / (sample_rate * 2)
                            if active:
                                quiet_since = None
                            elif quiet_since is None:
                                quiet_since = time.monotonic()
                            elif time.monotonic() - quiet_since >= args.hang:
                                break
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    if process.stdout:
                        process.stdout.close()
                    if clip is not None:
                        clip.close()
                        if recorded_seconds < args.min_clip:
                            clip_path.unlink(missing_ok=True)
                        else:
                            print(f"Saved: {clip_path}", flush=True)
                    pre_roll.clear()
                # With squelch enabled a quiet channel legitimately emits no
                # PCM. Only diagnose missing samples with squelch disabled.
                if (not received_pcm and not squelch
                        and process.returncode in (0, -signal.SIGTERM)):
                    print(
                        f"Warning: CH{index:02d} received no PCM within "
                        f"{args.startup_timeout:g}s; check USB/tuner health and squelch.",
                        flush=True,
                    )
                if process.returncode is not None and process.returncode > 0:
                    raise SystemExit(
                        "rtl_fm could not read the RTL-SDR; check that it is connected "
                        "and not in use by OpenWebRX."
                    )
    except KeyboardInterrupt:
        print("\nPMR scan stopped.", flush=True)
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)


def read_spectrum(path, bin_hz):
    samples = collections.defaultdict(list)
    with path.open(newline="", encoding="utf-8", errors="replace") as file:
        for row in csv.reader(file):
            if len(row) < 7:
                continue
            try:
                low = float(row[2])
                step = float(row[4])
                powers = [float(value) for value in row[6:] if value]
            except ValueError:
                continue
            for index, power in enumerate(powers):
                center = low + (index + 0.5) * step
                key = round(center / bin_hz) * bin_hz
                samples[key].append(power)
    ranked = []
    for frequency, powers in samples.items():
        powers.sort()
        ranked.append((powers[len(powers) // 2], frequency))
    ranked.sort(reverse=True)
    peaks = []
    for power, frequency in ranked:
        if all(abs(frequency - previous[1]) >= 25_000 for previous in peaks):
            peaks.append((power, frequency))
        if len(peaks) >= 8:
            break
    return peaks


def weather_scan(args):
    rtl_power = require_program("rtl_power")
    rtl_433 = require_program("rtl_433")
    out_dir = prepare_output_dir(args.output)
    run_id = stamp()
    rotate_output_files(
        out_dir,
        int(args.max_storage_gb * 1_000_000_000),
        max(args.duration, args.candidates * args.probe_seconds) * 20_000,
    )
    csv_path = out_dir / f"weather_spectrum_{run_id}.csv"

    command = [
        rtl_power,
        "-d", str(args.device),
        "-f", "430M:440M:12.5k",
        "-i", "2s",
        "-e", f"{args.duration}s",
        "-w", "hann-poisson",
        "-P",
        str(csv_path),
    ]
    print(f"Sweeping 430–440 MHz for {args.duration}s; output: {csv_path}", flush=True)
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(
            f"rtl_power failed (exit {exc.returncode}); check that the RTL-SDR is connected "
            "and not in use by OpenWebRX."
        ) from exc
    csv_path.chmod(0o600)

    peaks = read_spectrum(csv_path, 12_500)
    if not peaks:
        print("No spectrum rows were collected.", flush=True)
        return
    print("Strongest separated spectrum peaks (candidates, not station IDs):", flush=True)
    for power, frequency in peaks:
        print(f"  {frequency / 1_000_000:.5f} MHz  median {power:.1f} dB", flush=True)

    candidates = []
    for frequency in [433_920_000, 434_000_000] + [freq for _, freq in peaks]:
        frequency = int(round(frequency / 1_000) * 1_000)
        if all(abs(frequency - existing) >= 12_500 for existing in candidates):
            candidates.append(frequency)
        if len(candidates) >= args.candidates:
            break
    print(
        f"Trying rtl_433 decoding at {len(candidates)} candidate frequencies "
        f"({args.probe_seconds}s each).",
        flush=True,
    )
    decoded_logs = []
    for frequency in candidates:
        freq_mhz = frequency / 1_000_000
        log_path = out_dir / f"weather_decode_{run_id}_{freq_mhz:.5f}MHz.jsonl"
        print(f"  Decode probe: {freq_mhz:.5f} MHz", flush=True)
        decode = [
            rtl_433,
            "-d", str(args.device),
            "-f", str(frequency),
            "-T", f"{args.probe_seconds}s",
            "-F", "json",
            "-M", "time:utc",
        ]
        with log_path.open("w", encoding="utf-8") as output:
            log_path.chmod(0o600)
            result = subprocess.run(decode, stdout=output, check=False)
        if result.returncode:
            print(
                f"rtl_433 exited with {result.returncode} at "
                f"{freq_mhz:.5f} MHz; check tuner availability.",
                flush=True,
            )
            break
        if log_path.stat().st_size:
            decoded_logs.append(log_path)
    if decoded_logs:
        print("Decoded frames by frequency:", flush=True)
        for log_path in decoded_logs:
            print(f"  {log_path}", flush=True)
    else:
        print(
            "No supported weather-sensor packets decoded. The station may use another "
            "frequency/protocol, or the signal may have been absent during the probe.",
            flush=True,
        )


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)

    pmr = commands.add_parser("pmr", help="scan PMR446 and save detected audio clips")
    pmr.add_argument("--device", default="0", help="RTL-SDR device index or serial")
    pmr.add_argument("--output", default="./radio-recordings")
    pmr.add_argument("--dwell", type=float, default=0.75, help="initial seconds per channel")
    pmr.add_argument("--startup-timeout", type=float, default=2.0,
                     help="maximum seconds to wait for the first PCM from rtl_fm")
    pmr.add_argument("--squelch", type=int, default=35, help="rtl_fm squelch level")
    pmr.add_argument("--repeater-squelch", type=int, default=150,
                     help="separate rtl_fm squelch for 145.1125 MHz (REPEATER input)")
    pmr.add_argument("--downlink-squelch", type=int, default=150,
                     help="separate rtl_fm squelch for scheduled 145.7125 MHz output")
    pmr.add_argument("--threshold", type=float, default=-48.0, help="audio activity threshold in dBFS")
    pmr.add_argument("--cb-threshold", type=float, default=-36.0,
                     help="independent USB audio opening threshold in dBFS")
    pmr.add_argument("--cb-open-seconds", type=float, default=0.25,
                     help="continuous above-threshold USB audio needed to start recording")
    pmr.add_argument("--gain", default="auto", help="RTL-SDR tuner gain, or auto")
    pmr.add_argument("--warmup", type=float, default=0.25, help="ignore tuner settling audio")
    pmr.add_argument("--pre-roll", type=float, default=0.25)
    pmr.add_argument("--hang", type=float, default=2.0, help="silence duration before closing a clip")
    pmr.add_argument("--max-record", type=float, default=180.0, help="maximum clip duration")
    pmr.add_argument("--min-clip", type=float, default=0.35)
    pmr.add_argument(
        "--max-storage-gb", type=float, default=DEFAULT_MAX_STORAGE_GB,
        help="maximum combined size of radio files; oldest files rotate out",
    )
    pmr.set_defaults(run=pmr_scan)

    weather = commands.add_parser("weather", help="survey 430-440 MHz and try rtl_433 decoding")
    weather.add_argument("--device", default="0", help="RTL-SDR device index or serial")
    weather.add_argument("--output", default="./radio-recordings")
    weather.add_argument("--duration", type=int, default=60, help="spectrum sweep duration in seconds")
    weather.add_argument("--candidates", type=int, default=4, help="number of peaks to probe")
    weather.add_argument("--probe-seconds", type=int, default=20)
    weather.add_argument(
        "--max-storage-gb", type=float, default=DEFAULT_MAX_STORAGE_GB,
        help="maximum combined size of radio files; oldest files rotate out",
    )
    weather.set_defaults(run=weather_scan)
    return parser


def main():
    args = build_parser().parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
