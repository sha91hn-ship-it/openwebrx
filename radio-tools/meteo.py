#!/usr/bin/env python3
"""Automated Meteor LRPT scheduling and raw CU8 capture for one RTL-SDR."""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import logging
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent / "meteo-state"
CONFIG_PATH = Path(__file__).resolve().with_name("meteo-config.json")
SCHEDULE = ROOT / "schedule.json"
TARGETS = ROOT / "recording-targets.json"
UTC = dt.timezone.utc
LOG = logging.getLogger("meteo")


def load_config(path: Path = CONFIG_PATH) -> dict:
    config = json.loads(path.read_text())
    if config["format"] != "cu8":
        raise ValueError("This recorder only writes raw unsigned complex 8-bit IQ (cu8)")
    if config["sample_rate"] not in config["supported_sample_rates"]:
        raise ValueError("sample_rate must be one of supported_sample_rates")
    if config["frequency_shift_hz"] != 0:
        raise ValueError("The selected workflow requires zero frequency shift")
    if not 0 <= config["station"]["latitude"] <= 90:
        raise ValueError("Invalid station latitude")
    if not -180 <= config["station"]["longitude"] <= 180:
        raise ValueError("Invalid station longitude")
    return config


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    os.replace(temporary, path)


def iso_utc(stamp: float | dt.datetime) -> str:
    if isinstance(stamp, (int, float)):
        stamp = dt.datetime.fromtimestamp(stamp, UTC)
    return stamp.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_tle(text: str, norad: int) -> tuple[str, str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    one = next((line for line in lines if line.startswith(f"1 {norad}U")), None)
    two = next((line for line in lines if line.startswith(f"2 {norad} ")), None)
    if one is None or two is None or len(one) < 69 or len(two) < 69:
        raise ValueError(f"TLE does not contain valid element lines for NORAD {norad}")
    for line in (one, two):
        checksum = sum(int(char) if char.isdigit() else int(char == "-") for char in line[:68]) % 10
        if not line[68].isdigit() or checksum != int(line[68]):
            raise ValueError(f"TLE checksum failed for NORAD {norad}")
    return one, two


def tle_epoch(line1: str) -> dt.datetime:
    """Parse the standard TLE epoch field (YYDDD.dddddddd) as UTC."""
    year2 = int(line1[18:20])
    year = 2000 + year2 if year2 < 57 else 1900 + year2
    day = float(line1[20:32])
    return dt.datetime(year, 1, 1, tzinfo=UTC) + dt.timedelta(days=day - 1)


def expected_cu8_bytes(duration_seconds: float, sample_rate: int) -> int:
    """CU8 stores one unsigned I byte and one unsigned Q byte per complex sample."""
    return max(0, int(duration_seconds * sample_rate * 2))


def rtl_command(config: dict, frequency_hz: int, output: Path) -> list[str]:
    return ["rtl_sdr", "-d", config["rtl_sdr_device_serial"], "-f", str(frequency_hz),
            "-s", str(config["sample_rate"]), "-g", str(config["gain_db"]),
            "-p", str(config["ppm_correction"]), str(output)]


def evaluate_decode(return_code: int, output_dir: Path, log_text: str) -> dict:
    """A zero exit code alone is never considered successful decoding."""
    cadu = list(output_dir.rglob("*.cadu")) if output_dir.exists() else []
    cadu_bytes = sum(path.stat().st_size for path in cadu if path.is_file())
    image_exts = {".png", ".bmp", ".tif", ".tiff", ".jpg", ".jpeg"}
    images = [path for path in output_dir.rglob("*") if path.is_file() and path.suffix.lower() in image_exts] \
        if output_dir.exists() else []
    sync_text = log_text.lower()
    viterbi_sync = "viterbi" in sync_text and any(word in sync_text for word in ("sync", "lock"))
    deframer_sync = "deframer" in sync_text and any(word in sync_text for word in ("sync", "lock"))
    frame_match = re.search(r"(?:valid\s+)?(?:cadu\s+)?frames?\s*[:=]\s*(\d+)", log_text, re.I)
    frames = int(frame_match.group(1)) if frame_match else None
    success = (return_code == 0 and viterbi_sync and deframer_sync and cadu_bytes > 0
               and frames is not None and frames > 0 and bool(images))
    return {"status": "decoded" if success else "failed", "return_code": return_code,
            "viterbi_sync_reported": viterbi_sync, "deframer_sync_reported": deframer_sync,
            "valid_frame_count": frames, "cadu_bytes": cadu_bytes,
            "cadu_files": [str(path) for path in cadu],
            "image_files": [str(path) for path in images],
            "reason": None if success else "Requires non-empty CADU plus generated image; zero-byte CADU or no image is failure."}


def run_satdump(raw: Path, base: Path, config: dict, sample_rate: int) -> dict:
    satdump = config["satdump"]
    pipeline = satdump["pipeline"]
    if not satdump.get("automatic_processing"):
        return {"status": "disabled", "pipeline": pipeline}
    if not satdump.get("runtime_compatible_build_confirmed"):
        return {"status": "unavailable", "pipeline": pipeline,
                "reason": satdump.get("known_runtime_issue", "SatDump runtime compatibility not confirmed")}
    output = base.parent / (base.name + "_decoded")
    output.mkdir(exist_ok=True)
    log_path = base.with_suffix(".decode.log")
    command = ["satdump", "pipeline", pipeline, "baseband", str(raw), str(output),
               "--samplerate", str(sample_rate), "--baseband_format", "cu8"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
        log_text = result.stdout + "\n" + result.stderr
        log_path.write_text(log_text)
        assessment = evaluate_decode(result.returncode, output, log_text)
        assessment.update({"pipeline": pipeline, "log": str(log_path)})
        return assessment
    except (OSError, subprocess.SubprocessError) as exc:
        log_path.write_text(repr(exc) + "\n")
        return {"status": "unavailable", "pipeline": pipeline, "log": str(log_path), "reason": repr(exc)}


def refresh_tle(sat: dict, now: dt.datetime, config: dict, force: bool = False) -> dict:
    ROOT.mkdir(parents=True, exist_ok=True)
    norad = sat["norad"]
    cache = ROOT / f"{norad}.tle"
    metadata_path = ROOT / f"{norad}.tle.json"
    url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=TLE"
    cached_text = cache.read_text() if cache.exists() else ""
    cached_meta = {}
    if metadata_path.exists():
        try:
            cached_meta = json.loads(metadata_path.read_text())
        except (OSError, ValueError):
            LOG.warning("Ignoring damaged TLE metadata for %s", sat["name"])
    fetched = cached_meta.get("fetched_at_utc")
    last_fetch = dt.datetime.fromisoformat(fetched.replace("Z", "+00:00")) if fetched else None
    refresh_after = config["tle_refresh_seconds"]
    should_fetch = force or not cached_text or last_fetch is None or (now - last_fetch).total_seconds() >= refresh_after
    source_status = "cached"
    if should_fetch:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Meteor-LRPT-recorder/2"})
            with urllib.request.urlopen(request, timeout=30) as response:
                fresh_text = response.read().decode("ascii")
            line1, line2 = parse_tle(fresh_text, norad)
            cache.write_text("METEOR " + sat["name"] + "\n" + line1 + "\n" + line2 + "\n")
            cached_text = cache.read_text()
            fetched = iso_utc(now)
            cached_meta = {"norad": norad, "url": url, "fetched_at_utc": fetched,
                           "tle_epoch_utc": iso_utc(tle_epoch(line1))}
            save(metadata_path, cached_meta)
            source_status = "fresh"
            LOG.info("Refreshed CelesTrak TLE for %s; epoch %s", sat["name"], cached_meta["tle_epoch_utc"])
        except Exception as exc:
            source_status = "refresh_failed_using_cache" if cached_text else "unavailable"
            LOG.warning("CelesTrak TLE refresh failed for %s: %s", sat["name"], exc)
    if not cached_text:
        raise RuntimeError(f"No TLE available for {sat['name']} ({norad})")
    line1, line2 = parse_tle(cached_text, norad)
    epoch = tle_epoch(line1)
    age = abs((now - epoch).total_seconds())
    fetched_at = cached_meta.get("fetched_at_utc")
    if age > config["tle_max_age_seconds"]:
        raise RuntimeError(f"TLE for {sat['name']} is older than the configured seven-day limit")
    if age > refresh_after:
        LOG.warning("TLE epoch for %s is %.1f hours old", sat["name"], age / 3600)
    return {"line1": line1, "line2": line2, "epoch": iso_utc(epoch),
            "url": url, "fetched_at_utc": fetched_at, "source_status": source_status,
            "age_seconds": round(age)}


def probe_transmitter_status(config: dict, now: dt.datetime) -> dict:
    """Probe the community status page but never infer ON from a non-live page."""
    url = config["status_source_url"]
    result = {"state": "UNKNOWN", "source": url, "checked_at_utc": iso_utc(now),
              "reason": "No timestamped, machine-readable per-satellite live status was available."}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Meteor-LRPT-recorder/2"})
        with urllib.request.urlopen(request, timeout=12) as response:
            body = response.read(8192)
            result["http_status"] = response.status
            result["source_reachable"] = bool(body)
    except (OSError, urllib.error.URLError) as exc:
        result["source_reachable"] = False
        result["reason"] = f"Status source could not be checked: {exc}"
    return result


def _altaz(satellite, observer, ts, stamp: dt.datetime) -> tuple[float, float]:
    topocentric = (satellite - observer).at(ts.from_datetime(stamp))
    altitude, azimuth, _ = topocentric.altaz()
    return float(altitude.degrees), float(azimuth.degrees)


def _crossing(satellite, observer, ts, lo: dt.datetime, hi: dt.datetime,
              target: float, rising: bool) -> dt.datetime:
    """Bisect a monotonic altitude segment to find its target crossing."""
    for _ in range(36):
        mid = lo + (hi - lo) / 2
        elevation, _ = _altaz(satellite, observer, ts, mid)
        if (elevation < target) == rising:
            lo = mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def predict_passes(sat: dict, tle: dict, config: dict, now: dt.datetime) -> list[dict]:
    from skyfield.api import EarthSatellite, load, wgs84

    station = config["station"]
    ts = load.timescale(builtin=True)
    observer = wgs84.latlon(station["latitude"], station["longitude"], elevation_m=station["altitude_m"])
    satellite = EarthSatellite(tle["line1"], tle["line2"], sat["name"], ts)
    beginning = now - dt.timedelta(hours=2)
    ending = now + dt.timedelta(hours=config["lookahead_hours"])
    times, events = satellite.find_events(observer, ts.from_datetime(beginning), ts.from_datetime(ending),
                                          altitude_degrees=config["minimum_visible_elevation_deg"])
    rows = []
    aos = None
    tca = None
    peak = None
    for instant, event in zip(times, events):
        stamp = instant.utc_datetime().replace(tzinfo=UTC)
        if event == 0:
            aos = stamp
            tca = None
            peak = None
        elif event == 1 and aos is not None:
            tca = stamp
            peak, _ = _altaz(satellite, observer, ts, stamp)
        elif event == 2 and aos is not None and tca is not None and peak is not None:
            los = stamp
            aos_az, _ = _altaz(satellite, observer, ts, aos)
            _, los_az = _altaz(satellite, observer, ts, los)
            if peak >= config["record_elevation_deg"]:
                crossing_up = _crossing(satellite, observer, ts, aos, tca,
                                        config["record_elevation_deg"], True)
                crossing_down = _crossing(satellite, observer, ts, tca, los,
                                          config["record_elevation_deg"], False)
                record_start = crossing_up - dt.timedelta(seconds=config["record_margin_seconds"])
                record_end = crossing_down + dt.timedelta(seconds=config["record_margin_seconds"])
            else:
                # List low passes, but don't invent 10-degree recording crossings.
                record_start, record_end = aos, los
            if record_end.timestamp() >= now.timestamp():
                threshold = config["minimum_peak_for_recording_deg"]
                suitability = ("RECOMMENDED" if peak >= config["recommended_peak_elevation_deg"]
                               else "PREFERRED" if peak >= config["preferred_peak_elevation_deg"]
                               else "LOW")
                rows.append({
                    "satellite": sat["name"], "norad": sat["norad"],
                    "frequency_hz": sat["frequency_hz"],
                    "frequency_evidence": sat["frequency_evidence"],
                    "frequency_evidence_url": sat["frequency_evidence_url"],
                    "transmitter_status": "UNKNOWN",
                    "status_source_url": config["status_source_url"],
                    "tle_source_url": tle["url"], "tle_fetched_at_utc": tle["fetched_at_utc"],
                    "tle_epoch_utc": tle["epoch"], "tle_age_seconds": tle["age_seconds"],
                    "aos_utc": iso_utc(aos), "tca_utc": iso_utc(tca), "los_utc": iso_utc(los),
                    "aos_azimuth_deg": round(aos_az % 360, 1),
                    "los_azimuth_deg": round(los_az % 360, 1),
                    "max_elevation_deg": round(peak, 1),
                    "suitability": suitability,
                    "visible_duration_seconds": round((los-aos).total_seconds()),
                    "record_start_utc": iso_utc(record_start),
                    "record_end_utc": iso_utc(record_end),
                    "late_start_seconds": max(0, round((now-record_start).total_seconds())),
                    "status": "PLANNED"
                })
            aos = tca = peak = None
    return rows


def _select_non_overlapping(passes: list[dict], config: dict) -> list[dict]:
    for p in passes:
        p["selected_for_recording"] = False
        if (p["max_elevation_deg"] < config["minimum_peak_for_recording_deg"]
                and not config["record_below_30_deg"]):
            p["status"] = "SKIPPED_LOW_ELEVATION"
        else:
            p["status"] = "CANDIDATE"
    items = [p for p in passes if p["status"] == "CANDIDATE"]
    items.sort(key=lambda p: dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00")))
    ends = [dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00")) for p in items]
    starts = [dt.datetime.fromisoformat(p["record_start_utc"].replace("Z", "+00:00")) for p in items]
    previous = []
    for i, start in enumerate(starts):
        j = i - 1
        while j >= 0 and ends[j] > start:
            j -= 1
        previous.append(j)
    # Elevation dominates; confirmed ON status would receive a strong priority boost.
    weights = [p["max_elevation_deg"] + (10000 if p["transmitter_status"] == "ON" else 0)
               for p in items]
    best = [0.0] * (len(items) + 1)
    take = [False] * len(items)
    for i in range(1, len(items) + 1):
        with_item = weights[i-1] + best[previous[i-1] + 1]
        without_item = best[i-1]
        best[i] = max(with_item, without_item)
        take[i-1] = with_item > without_item
    chosen = set()
    i = len(items)
    while i:
        if take[i-1] and weights[i-1] + best[previous[i-1]+1] >= best[i-1]:
            chosen.add(i-1)
            i = previous[i-1] + 1
        else:
            i -= 1
    for index, p in enumerate(items):
        if index in chosen:
            p["selected_for_recording"] = True
            p["status"] = "PLANNED_TX_UNKNOWN"
        else:
            p["status"] = "SKIPPED_CONFLICT"
    limit = config.get("max_recordings_in_lookahead")
    if limit is not None:
        ranking = sorted(items, key=lambda p: (p["transmitter_status"] == "ON", p["max_elevation_deg"]),
                         reverse=True)
        selected = []
        for p in ranking:
            if len(selected) >= limit:
                break
            start = dt.datetime.fromisoformat(p["record_start_utc"].replace("Z", "+00:00"))
            end = dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00"))
            overlaps = any(start < dt.datetime.fromisoformat(q["record_end_utc"].replace("Z", "+00:00"))
                           and end > dt.datetime.fromisoformat(q["record_start_utc"].replace("Z", "+00:00"))
                           for q in selected)
            if not overlaps:
                selected.append(p)
        selected_ids = {id(p) for p in selected}
        for p in items:
            if id(p) in selected_ids:
                p["selected_for_recording"] = True
                p["status"] = "PLANNED_TX_UNKNOWN"
            else:
                p["selected_for_recording"] = False
                p["status"] = "SKIPPED_CONFLICT" if any(
                    dt.datetime.fromisoformat(p["record_start_utc"].replace("Z", "+00:00"))
                    < dt.datetime.fromisoformat(q["record_end_utc"].replace("Z", "+00:00"))
                    and dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00"))
                    > dt.datetime.fromisoformat(q["record_start_utc"].replace("Z", "+00:00"))
                    for q in selected) else "SKIPPED_BELOW_TOP_N"
    return passes


def _apply_targets(passes: list[dict], targets: list[dict], now: dt.datetime,
                   tolerance_seconds: int = 1200) -> list[dict]:
    """Match the fixed initial top-pass picks to hourly refreshed SGP4 predictions."""
    for p in passes:
        p["selected_for_recording"] = False
        if p["max_elevation_deg"] < 30:
            p["status"] = "SKIPPED_LOW_ELEVATION"
        else:
            p["status"] = "NOT_IN_SELECTED_TOP_FIVE"
    retained = []
    for target in targets:
        target_end = dt.datetime.fromisoformat(target["record_end_utc"].replace("Z", "+00:00"))
        if target_end <= now:
            continue
        target_tca = dt.datetime.fromisoformat(target["tca_utc"].replace("Z", "+00:00"))
        matches = [p for p in passes if p["norad"] == target["norad"]
                   and abs((dt.datetime.fromisoformat(p["tca_utc"].replace("Z", "+00:00"))
                            - target_tca).total_seconds()) <= tolerance_seconds]
        if not matches:
            retained.append(target)
            continue
        match = min(matches, key=lambda p: abs((dt.datetime.fromisoformat(
            p["tca_utc"].replace("Z", "+00:00")) - target_tca).total_seconds()))
        if match["max_elevation_deg"] < 30:
            retained.append(target)
            continue
        match["selected_for_recording"] = True
        match["status"] = "PLANNED_TOP_FIVE_TX_UNKNOWN"
        retained.append({"norad": match["norad"], "satellite": match["satellite"],
                         "tca_utc": match["tca_utc"], "record_start_utc": match["record_start_utc"],
                         "record_end_utc": match["record_end_utc"],
                         "max_elevation_deg": match["max_elevation_deg"]})
    return retained


def plan(now: dt.datetime | None = None, force_tle: bool = False, reselect_targets: bool = False) -> dict:
    config = load_config()
    now = (now or dt.datetime.now(UTC)).astimezone(UTC)
    ROOT.mkdir(parents=True, exist_ok=True)
    status_probe = probe_transmitter_status(config, now)
    all_passes = []
    satellite_errors = []
    for sat in config["satellites"]:
        try:
            tle = refresh_tle(sat, now, config, force=force_tle)
            all_passes.extend(predict_passes(sat, tle, config, now))
        except Exception as exc:
            LOG.exception("Could not schedule %s", sat["name"])
            satellite_errors.append({"satellite": sat["name"], "error": str(exc)})
    all_passes.sort(key=lambda p: p["record_start_utc"])
    for p in all_passes:
        p["status_checked_at_utc"] = status_probe["checked_at_utc"]
        p["status_source_reachable"] = status_probe.get("source_reachable")
        p["transmitter_status_reason"] = status_probe["reason"]
    if config.get("lock_top_pass_targets"):
        if TARGETS.exists() and not reselect_targets:
            targets = json.loads(TARGETS.read_text())
            targets = _apply_targets(all_passes, targets, now)
            save(TARGETS, targets)
        else:
            _select_non_overlapping(all_passes, config)
            targets = [{"norad": p["norad"], "satellite": p["satellite"],
                        "tca_utc": p["tca_utc"], "record_start_utc": p["record_start_utc"],
                        "record_end_utc": p["record_end_utc"],
                        "max_elevation_deg": p["max_elevation_deg"]}
                       for p in all_passes if p.get("selected_for_recording")]
            save(TARGETS, targets)
    else:
        _select_non_overlapping(all_passes, config)
    data = {
        "schema_version": 2,
        "generated_utc": iso_utc(now),
        "expires_utc": iso_utc(now + dt.timedelta(hours=6)),
        "lookahead_hours": config["lookahead_hours"],
        "station": config["station"],
        "status_check": status_probe,
        "satellite_errors": satellite_errors,
        "passes": all_passes,
    }
    save(SCHEDULE, data)
    LOG.info("Predicted %d passes in the next %d hours; TX state remains UNKNOWN unless verified.",
             len(all_passes), config["lookahead_hours"])
    return data


def due(now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    try:
        data = json.loads(SCHEDULE.read_text())
        if dt.datetime.fromisoformat(data["expires_utc"].replace("Z", "+00:00")).timestamp() < now:
            return []
        return [p for p in data["passes"] if p.get("selected_for_recording")
                and dt.datetime.fromisoformat(p["record_start_utc"].replace("Z", "+00:00")).timestamp() <= now
                < dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00")).timestamp()]
    except (OSError, ValueError, KeyError, TypeError):
        return []


def _local(stamp: str, zone: ZoneInfo) -> str:
    value = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return value.astimezone(zone).strftime("%Y-%m-%d %H:%M:%S %Z") + f" ({stamp})"


def render_table(data: dict) -> str:
    config = load_config()
    zone = ZoneInfo(config["station"]["timezone"])
    rows = sorted(data.get("passes", []), key=lambda p: p["record_start_utc"])
    lines = ["Pass schedule — local time and UTC", "Satellite | Freq | AOS | TCA | Peak | LOS | Record | Rank | State"]
    for p in rows:
        lines.append(" | ".join([
            p["satellite"], f"{p['frequency_hz']/1e6:.3f} MHz",
            _local(p["aos_utc"], zone), _local(p["tca_utc"], zone),
            f"{p['max_elevation_deg']:.1f}°",
            _local(p["los_utc"], zone),
            _local(p["record_start_utc"], zone) + " – " + _local(p["record_end_utc"], zone),
            p.get("suitability", "UNKNOWN"), p["status"] + " / TX " + p["transmitter_status"]
        ]))
    return "\n".join(lines)


def _free_space_check(out: Path, reserve_bytes: int, config: dict, used_bytes: int) -> None:
    usage = shutil.disk_usage(out)
    if used_bytes + reserve_bytes > config["storage_limit_bytes"]:
        raise RuntimeError("Meteor recording storage cap reached; previous files were preserved")
    if usage.free < reserve_bytes + config["minimum_free_bytes"]:
        raise RuntimeError("Not enough free space for this scheduled capture; previous files were preserved")


def _spectrum(raw: Path, base: Path, frequency_hz: int, rate: int) -> dict:
    """Write an optional averaged PSD CSV and coarse, non-SatDump SNR estimate."""
    try:
        import numpy as np
    except ImportError:
        return {"spectrum_status": "unavailable", "reason": "numpy is not installed"}
    size = raw.stat().st_size
    sample_bytes = 2
    take_bytes = min(size - size % sample_bytes, 32 * 1024 * 1024)
    if take_bytes < 1024 * 1024:
        return {"spectrum_status": "unavailable", "reason": "less than 1 MiB of IQ available"}
    with raw.open("rb") as source:
        source.seek(size - take_bytes)
        iq = np.frombuffer(source.read(take_bytes), dtype=np.uint8).astype(np.float32)
    iq = iq[0::2] - 127.5 + 1j * (iq[1::2] - 127.5)
    fft_size = 8192
    blocks = len(iq) // fft_size
    iq = iq[:blocks * fft_size].reshape(blocks, fft_size)
    window = np.hanning(fft_size).astype(np.float32)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(iq * window, axis=1), axes=1)) ** 2, axis=0)
    psd /= float(np.sum(window ** 2))
    offsets = np.fft.fftshift(np.fft.fftfreq(fft_size, d=1/rate))
    out_csv = base.with_suffix(".spectrum.csv")
    with out_csv.open("w") as out:
        out.write("offset_hz,absolute_frequency_hz,power_dbfs_relative\n")
        peak = float(np.max(psd))
        for offset, value in zip(offsets, psd):
            db = 10 * math.log10(max(float(value) / peak, 1e-15))
            out.write(f"{offset:.2f},{frequency_hz+offset:.2f},{db:.3f}\n")
    signal_bins = (np.abs(offsets) <= 45000) & (np.abs(offsets) >= 1500)
    noise_bins = (np.abs(offsets) >= 100000) & (np.abs(offsets) <= min(rate/2-1000, 300000))
    snr = None
    if signal_bins.any() and noise_bins.any():
        sig = max(float(np.mean(psd[signal_bins])), 1e-30)
        noise = max(float(np.mean(psd[noise_bins])), 1e-30)
        snr = round(10 * math.log10(sig / noise), 2)
    result = {"spectrum_status": "saved", "spectrum_csv": str(out_csv),
              "spectrum_method": "averaged 8192-point FFT of final IQ segment",
              "coarse_spectral_snr_estimate_db": snr,
              "snr_note": "Local PSD estimate only; not SatDump demodulator SNR or proof of satellite lock."}
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axis = plt.subplots(figsize=(12, 4))
        axis.plot((frequency_hz + offsets) / 1e6, 10*np.log10(np.maximum(psd/peak, 1e-15)))
        axis.set(xlabel="Frequency (MHz)", ylabel="Relative power (dB)",
                 title="Meteor LRPT baseband spectrum — coarse estimate")
        axis.grid(True, alpha=.25)
        fig.tight_layout()
        png = base.with_suffix(".spectrum.png")
        fig.savefig(png, dpi=120)
        plt.close(fig)
        result["spectrum_png"] = str(png)
    except ImportError:
        result["spectrum_png_status"] = "matplotlib not installed"
    return result


def _capture_metadata(sat_pass: dict | None, config: dict, start: dt.datetime,
                      status_check: dict, test_seconds: float | None) -> dict:
    sat = next((s for s in config["satellites"] if sat_pass and s["norad"] == sat_pass["norad"]), None)
    if sat is None:
        sat = {"name": "Hardware-Test", "norad": None, "frequency_hz": config["satellites"][0]["frequency_hz"],
               "frequency_evidence": "configured test frequency", "frequency_evidence_url": None}
    return {
        "schema_version": 2,
        "satellite": {"name": sat["name"], "norad": sat["norad"],
                      "frequency_hz": sat["frequency_hz"],
                      "frequency_evidence": sat["frequency_evidence"],
                      "frequency_evidence_url": sat["frequency_evidence_url"]},
        "transmitter_status": {"state": "UNKNOWN", "source": status_check.get("source"),
                                "checked_at_utc": status_check.get("checked_at_utc"),
                                "reason": status_check.get("reason")},
        "station": config["station"],
        "tle": ({"source": sat_pass["tle_source_url"], "fetched_at_utc": sat_pass["tle_fetched_at_utc"],
                 "epoch_utc": sat_pass["tle_epoch_utc"]} if sat_pass else None),
        "pass": sat_pass,
        "planned_start_utc": sat_pass.get("record_start_utc") if sat_pass else None,
        "planned_end_utc": sat_pass.get("record_end_utc") if sat_pass else None,
        "actual_start_utc": iso_utc(start), "actual_end_utc": None,
        "center_frequency_hz": sat["frequency_hz"],
        "frequency_shift_hz": config["frequency_shift_hz"],
        "sample_rate_sps": config["sample_rate"],
        "format": "cu8", "iq_layout": "unsigned 8-bit I then Q, interleaved, headerless",
        "gain_mode": config["gain_mode"], "gain_db": config["gain_db"],
        "ppm_correction": config["ppm_correction"],
        "planned_duration_seconds": (round(
            (dt.datetime.fromisoformat(sat_pass["record_end_utc"].replace("Z", "+00:00"))
             - dt.datetime.fromisoformat(sat_pass["record_start_utc"].replace("Z", "+00:00"))).total_seconds(), 2
        ) if sat_pass else test_seconds),
        "verified_sample_rate_sps": None,
        "recording_status": "recording", "bytes": 0,
        "estimated_data_loss_seconds": None,
        "data_loss_note": "rtl_sdr CLI does not expose an exact missed-USB-sample counter; file-rate stalls are monitored.",
        "quality": {"status": "pending", "satdump_snr_db": None},
        "decode": {"status": "unavailable", "pipeline": config["satdump"]["pipeline"],
                   "reason": config["satdump"]["known_runtime_issue"]},
    }


def _check_startup(log_path: Path, process: subprocess.Popen, frequency: int, rate: int,
                   gain: float, deadline: float) -> None:
    required = {"device": False, "frequency": False, "rate": False, "gain": False}
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"rtl_sdr exited during startup with code {process.returncode}")
        try:
            text = log_path.read_text(errors="replace")
        except OSError:
            text = ""
        required["device"] = "Found 1 device(s)" in text or "Found device" in text
        required["frequency"] = f"Tuned to {frequency} Hz" in text
        required["rate"] = f"Sampling at {rate} S/s" in text
        required["gain"] = f"Tuner gain set to {gain:.2f} dB" in text
        if all(required.values()):
            return
        time.sleep(.25)
    raise RuntimeError(f"SDR startup checks did not pass: {required}")


def capture(test_seconds: float | None = None) -> None:
    config = load_config()
    active = due()
    if not active and test_seconds is None:
        return
    if len(active) > 1:
        active.sort(key=lambda p: (p["transmitter_status"] == "ON", p["max_elevation_deg"]), reverse=True)
    sat_pass = active[0] if active else None
    now = dt.datetime.now(UTC)
    scheduled_end = (dt.datetime.fromisoformat(sat_pass["record_end_utc"].replace("Z", "+00:00"))
                     if sat_pass else now + dt.timedelta(seconds=test_seconds))
    end_epoch = scheduled_end.timestamp()
    if test_seconds is not None:
        end_epoch = time.time() + test_seconds
    if end_epoch <= time.time():
        return
    rate = config["sample_rate"]
    expected_reserve = max(0, int((end_epoch - time.time() + 10) * rate * 2))
    out = Path(config["output_directory"])
    out.mkdir(parents=True, exist_ok=True)
    lock_path = out / ".meteo-capture.lock"
    with lock_path.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another Meteor capture already owns the SDR") from exc
        used = sum(p.stat().st_size for p in out.glob("meteo_*.cu8") if p.is_file())
        _free_space_check(out, expected_reserve, config, used)
        stamp = dt.datetime.now(UTC).strftime("%Y%m%d_%H%M%SZ")
        satellite_name = sat_pass["satellite"] if sat_pass else "hardware-test"
        frequency = sat_pass["frequency_hz"] if sat_pass else config["satellites"][0]["frequency_hz"]
        base = out / f"meteo_{stamp}_{satellite_name}_{frequency}Hz_{rate}sps"
        raw = base.with_suffix(".cu8")
        sidecar = base.with_suffix(".json")
        log_path = base.with_suffix(".log")
        status_check = {"state": "UNKNOWN", "source": config["status_source_url"],
                        "checked_at_utc": sat_pass.get("status_checked_at_utc") if sat_pass else iso_utc(now),
                        "source_reachable": sat_pass.get("status_source_reachable") if sat_pass else None,
                        "reason": sat_pass.get("transmitter_status_reason") if sat_pass else
                                  "No timestamped, machine-readable per-satellite live status was verified."}
        metadata = _capture_metadata(sat_pass, config, now, status_check, test_seconds)
        if sat_pass:
            scheduled_start = dt.datetime.fromisoformat(sat_pass["record_start_utc"].replace("Z", "+00:00"))
            metadata["late_start_seconds"] = max(0, round((now-scheduled_start).total_seconds()))
            if metadata["late_start_seconds"]:
                LOG.warning("Starting late by %s seconds for %s", metadata["late_start_seconds"], satellite_name)
        save(sidecar, metadata)
        command = rtl_command(config, frequency, raw)
        started_monotonic = time.monotonic()
        failure = None
        stop_requested = False

        def request_stop(_signum, _frame):
            nonlocal stop_requested
            stop_requested = True

        previous_term = signal.signal(signal.SIGTERM, request_stop)
        previous_int = signal.signal(signal.SIGINT, request_stop)
        try:
            with log_path.open("w", buffering=1) as log:
                log.write("METEOR recorder start\n")
                log.write(f"UTC start: {iso_utc(now)}\n")
                log.write(f"Pass transmitter status: UNKNOWN; checked {status_check['checked_at_utc']}; "
                          f"source: {status_check['source']}\n")
                log.write(f"Frequency evidence: {metadata['satellite']['frequency_evidence']}\n")
                log.write("Command: " + " ".join(command[:-1]) + " <IQ-output>\n")
                process = subprocess.Popen(command, stdout=log, stderr=log)
                _check_startup(log_path, process, frequency, rate, config["gain_db"], time.monotonic()+20)
                now = dt.datetime.now(UTC)
                started_monotonic = time.monotonic()
                metadata["actual_start_utc"] = iso_utc(now)
                metadata["verified_sample_rate_sps"] = rate
                metadata["recording_status"] = "recording"
                save(sidecar, metadata)
                last_size = 0
                last_growth = time.monotonic()
                while not stop_requested and time.time() < end_epoch:
                    if process.poll() is not None:
                        raise RuntimeError(f"rtl_sdr exited unexpectedly with {process.returncode}")
                    size = raw.stat().st_size if raw.exists() else 0
                    if size > last_size:
                        last_size = size
                        last_growth = time.monotonic()
                        elapsed = max(.001, time.monotonic() - started_monotonic)
                        expected = expected_cu8_bytes(elapsed, rate)
                        if size < expected * .65 and elapsed > 10:
                            raise RuntimeError("IQ file growth is below 65% of expected byte rate")
                    elif time.monotonic() - last_growth > 12:
                        raise RuntimeError("No IQ data growth for 12 seconds")
                    if time.monotonic() - started_monotonic >= 5:
                        elapsed = time.monotonic() - started_monotonic
                        actual_size = raw.stat().st_size if raw.exists() else 0
                        metadata["bytes"] = actual_size
                        metadata["duration_seconds"] = round(elapsed, 2)
                        save(sidecar, metadata)
                    time.sleep(.5)
                metadata["recording_status"] = "interrupted" if stop_requested else "captured"
        except Exception as exc:
            failure = exc
            metadata["recording_status"] = "failed"
            metadata["error"] = repr(exc)
            LOG.exception("Capture failed for %s", satellite_name)
        finally:
            if "process" in locals() and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            signal.signal(signal.SIGTERM, previous_term)
            signal.signal(signal.SIGINT, previous_int)
            ended = dt.datetime.now(UTC)
            duration = max(.001, time.monotonic() - started_monotonic)
            size = raw.stat().st_size if raw.exists() else 0
            expected_size = expected_cu8_bytes(duration, rate)
            metadata["actual_end_utc"] = iso_utc(ended)
            metadata["bytes"] = size
            metadata["duration_seconds"] = round(duration, 2)
            metadata["expected_bytes_for_duration"] = expected_size
            metadata["estimated_data_loss_seconds"] = round(max(0, expected_size-size)/(rate*2), 3)
            if metadata["recording_status"] == "captured" and raw.exists():
                try:
                    metadata["quality"].update(_spectrum(raw, base, frequency, rate))
                    metadata["quality"]["status"] = "measured_coarsely"
                except Exception as exc:
                    metadata["quality"] = {"status": "spectrum_error", "reason": repr(exc)}
                metadata["decode"] = run_satdump(raw, base, config, rate)
            elif metadata["recording_status"] == "interrupted":
                # Release the SDR promptly during web handover. Post-capture
                # analysis can be run later without holding the tuner.
                metadata["quality"] = {"status": "skipped_during_tuner_handover"}
                metadata["decode"] = {"status": "not_attempted_interrupted"}
            save(sidecar, metadata)
            with log_path.open("a") as log:
                log.write(f"\nActual end UTC: {metadata['actual_end_utc']}\n")
                log.write(f"Status: {metadata['recording_status']}\nBytes: {size}\n")
                log.write(f"Expected bytes: {expected_size}\nEstimated missing-data equivalent (s): "
                          f"{metadata['estimated_data_loss_seconds']}\n")
                log.write("Satellite transmission status: UNKNOWN (not verified by RF lock or live feed).\n")
            LOG.info("Capture %s: %s bytes in %.1f seconds; status=%s", raw.name, size, duration,
                     metadata["recording_status"])
        if failure:
            raise failure


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not argv or argv[0] in ("-h", "--help"):
        print("Usage: meteo.py plan [--force-tle] | table | capture | test SECONDS")
        return 0
    if argv[0] == "plan":
        data = plan(force_tle="--force-tle" in argv[1:], reselect_targets="--reselect-top" in argv[1:])
        print(render_table(data))
    elif argv[0] == "table":
        try:
            print(render_table(json.loads(SCHEDULE.read_text())))
        except (OSError, ValueError) as exc:
            LOG.error("No usable schedule: %s", exc)
            return 1
    elif argv[0] == "capture":
        capture()
    elif argv[0] == "test" and len(argv) == 2:
        capture(float(argv[1]))
    else:
        print("Unknown command", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
