import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import meteo
import rf_monitor
import pmr_idle_watch as watcher

UTC = dt.timezone.utc
TLE_57166 = (
    "METEOR-M2 3\n"
    "1 57166U 23091A   26287.26296103 -.00000013  00000+0  13089-4 0  9993\n"
    "2 57166  98.5946 339.7207 0004107 168.4229 191.7045 14.24054179171466\n"
)


def candidate(name, start, end, peak, norad=57166, state="UNKNOWN"):
    return {"satellite": name, "norad": norad, "transmitter_status": state,
            "max_elevation_deg": peak, "record_start_utc": meteo.iso_utc(start),
            "record_end_utc": meteo.iso_utc(end), "selected_for_recording": False,
            "status": "PLANNED"}


class MeteoTests(unittest.TestCase):
    def test_tle_identity_epoch_and_checksum_validation(self):
        line1, line2 = meteo.parse_tle(TLE_57166, 57166)
        self.assertEqual(line1[2:7], "57166")
        self.assertEqual(meteo.tle_epoch(line1), dt.datetime(2026, 10, 14, 6, 18, 39, 832992, tzinfo=UTC))
        with self.assertRaises(ValueError):
            meteo.parse_tle(TLE_57166, 59051)
        bad = TLE_57166.replace("9993", "9990")
        with self.assertRaises(ValueError):
            meteo.parse_tle(bad, 57166)

    def test_fresh_tle_plan_has_configured_horizon_and_real_sgp4_pass_details(self):
        cfg = meteo.load_config()
        sat = cfg["satellites"][0]
        line1, line2 = meteo.parse_tle(TLE_57166, sat["norad"])
        tle = {"line1": line1, "line2": line2, "url": "https://celestrak.org/test",
               "fetched_at_utc": "2026-10-14T06:20:00Z", "epoch": meteo.iso_utc(meteo.tle_epoch(line1)),
               "age_seconds": 0}
        now = dt.datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
        passes = meteo.predict_passes(sat, tle, cfg, now)
        self.assertTrue(passes)
        self.assertLessEqual(dt.datetime.fromisoformat(passes[-1]["aos_utc"].replace("Z", "+00:00")),
                             now + dt.timedelta(hours=cfg["lookahead_hours"]))
        p = next(x for x in passes if x["max_elevation_deg"] >= 30)
        self.assertEqual(p["frequency_hz"], 137900000)
        self.assertIn("aos_azimuth_deg", p)
        self.assertIn("los_azimuth_deg", p)
        self.assertGreater(p["visible_duration_seconds"], 0)
        self.assertEqual(p["transmitter_status"], "UNKNOWN")

    def test_record_window_uses_10_degree_crossings_and_two_minute_margins(self):
        cfg = meteo.load_config()
        sat = cfg["satellites"][0]
        line1, line2 = meteo.parse_tle(TLE_57166, sat["norad"])
        tle = {"line1": line1, "line2": line2, "url": "source", "fetched_at_utc": None,
               "epoch": "2026-10-14T06:18:39Z", "age_seconds": 0}
        now = dt.datetime(2026, 10, 15, 17, 0, tzinfo=UTC)
        p = next(x for x in meteo.predict_passes(sat, tle, cfg, now)
                 if x["max_elevation_deg"] >= 30)
        start = dt.datetime.fromisoformat(p["record_start_utc"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(p["record_end_utc"].replace("Z", "+00:00"))
        from skyfield.api import EarthSatellite, load, wgs84
        ts = load.timescale(builtin=True)
        observer = wgs84.latlon(cfg["station"]["latitude"], cfg["station"]["longitude"],
                                 elevation_m=cfg["station"]["altitude_m"])
        orbital = EarthSatellite(line1, line2, sat["name"], ts)
        up, _ = meteo._altaz(orbital, observer, ts, start + dt.timedelta(seconds=120))
        down, _ = meteo._altaz(orbital, observer, ts, end - dt.timedelta(seconds=120))
        self.assertAlmostEqual(up, 10, delta=.02)
        self.assertAlmostEqual(down, 10, delta=.02)
        self.assertEqual(cfg["record_elevation_deg"], 10)

    def test_10_30_50_degree_capture_and_suitability_thresholds(self):
        now = dt.datetime(2026, 10, 15, tzinfo=UTC)
        passes = [candidate(f"s{i}", now + dt.timedelta(hours=i*2), now + dt.timedelta(hours=i*2+1), peak)
                  for i, peak in enumerate((10, 29.9, 30, 50))]
        meteo._select_non_overlapping(passes, meteo.load_config())
        self.assertEqual(passes[0]["status"], "SKIPPED_LOW_ELEVATION")
        self.assertEqual(passes[1]["status"], "SKIPPED_LOW_ELEVATION")
        self.assertTrue(passes[2]["selected_for_recording"])
        self.assertTrue(passes[3]["selected_for_recording"])
        self.assertEqual(meteo.expected_cu8_bytes(2, 1024000), 4096000)
        self.assertEqual(meteo.expected_cu8_bytes(2, 2048000), 8192000)

    def test_overlapping_passes_choose_the_higher_elevation_and_keep_other_passes(self):
        now = dt.datetime(2026, 10, 15, tzinfo=UTC)
        passes = [candidate("low", now, now+dt.timedelta(minutes=10), 35),
                  candidate("high", now+dt.timedelta(minutes=3), now+dt.timedelta(minutes=13), 73),
                  candidate("later", now+dt.timedelta(minutes=20), now+dt.timedelta(minutes=30), 40)]
        meteo._select_non_overlapping(passes, meteo.load_config())
        self.assertEqual([p["satellite"] for p in passes if p["selected_for_recording"]], ["high", "later"])

    def test_only_the_five_highest_non_overlapping_passes_are_selected(self):
        now = dt.datetime(2026, 10, 15, tzinfo=UTC)
        passes = [candidate(f"p{i}", now + dt.timedelta(hours=i),
                            now + dt.timedelta(hours=i, minutes=30), peak)
                  for i, peak in enumerate((31, 42, 85, 62, 74, 51, 39))]
        cfg = meteo.load_config()
        cfg["max_recordings_in_lookahead"] = 5
        meteo._select_non_overlapping(passes, cfg)
        selected = [p["max_elevation_deg"] for p in passes if p["selected_for_recording"]]
        self.assertEqual(selected, [42, 85, 62, 74, 51])
        self.assertEqual(sum(p["status"] == "SKIPPED_BELOW_TOP_N" for p in passes), 2)

    def test_locked_target_follows_only_its_matching_satellite_pass(self):
        now = dt.datetime(2026, 10, 25, 12, 0, tzinfo=UTC)
        target = {"norad": 57166, "satellite": "Meteor-M2-3",
                  "tca_utc": "2026-10-25T13:00:00.000Z",
                  "record_start_utc": "2026-10-25T12:50:00.000Z",
                  "record_end_utc": "2026-10-25T13:10:00.000Z"}
        wanted = {"norad": 57166, "satellite": "Meteor-M2-3", "max_elevation_deg": 70,
                  "tca_utc": "2026-10-25T13:00:20.000Z",
                  "record_start_utc": "2026-10-25T12:50:01.000Z",
                  "record_end_utc": "2026-10-25T13:10:01.000Z"}
        other = {"norad": 59051, "satellite": "Meteor-M2-4", "max_elevation_deg": 90,
                 "tca_utc": "2026-10-25T13:00:00.000Z",
                 "record_start_utc": "2026-10-25T12:50:00.000Z",
                 "record_end_utc": "2026-10-25T13:10:00.000Z"}
        retained = meteo._apply_targets([wanted, other], [target], now)
        self.assertTrue(wanted["selected_for_recording"])
        self.assertFalse(other["selected_for_recording"])
        self.assertEqual(retained[0]["tca_utc"], wanted["tca_utc"])

    def test_confirmed_active_transmitter_outweighs_unknown_overlapping_pass(self):
        now = dt.datetime(2026, 10, 15, tzinfo=UTC)
        passes = [candidate("unknown-high", now, now+dt.timedelta(minutes=10), 80),
                  candidate("active", now+dt.timedelta(minutes=1), now+dt.timedelta(minutes=9), 35,
                            norad=59051, state="ON")]
        meteo._select_non_overlapping(passes, meteo.load_config())
        self.assertTrue(passes[1]["selected_for_recording"])
        self.assertFalse(passes[0]["selected_for_recording"])

    def test_tuner_command_uses_single_satellite_frequency_and_supported_rates(self):
        cfg = meteo.load_config()
        command = meteo.rtl_command(cfg, 137900000, Path("test.cu8"))
        self.assertEqual(command[command.index("-f") + 1], "137900000")
        self.assertEqual(command[command.index("-s") + 1], "1024000")
        self.assertEqual(command[command.index("-g") + 1], "38.6")
        cfg["sample_rate"] = 2048000
        self.assertIn(2048000, cfg["supported_sample_rates"])
        self.assertEqual(cfg["frequency_shift_hz"], 0)

    def test_cu8_file_size_formula_and_metadata_layout(self):
        self.assertEqual(meteo.expected_cu8_bytes(10, 1024000), 20480000)
        self.assertEqual(meteo.expected_cu8_bytes(10, 2048000), 40960000)
        cfg = meteo.load_config()
        meta = meteo._capture_metadata(None, cfg, dt.datetime(2026, 10, 15, tzinfo=UTC),
                                       {"source": "x", "checked_at_utc": "now", "reason": "unknown"}, None)
        self.assertEqual(meta["format"], "cu8")
        self.assertIn("unsigned", meta["iq_layout"])
        self.assertEqual(meta["frequency_shift_hz"], 0)

    def test_stale_or_missing_tle_is_never_used_as_fresh(self):
        cfg = meteo.load_config()
        cfg["tle_max_age_seconds"] = 60
        sat = cfg["satellites"][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "57166.tle").write_text(TLE_57166)
            (root / "57166.tle.json").write_text(json.dumps({"fetched_at_utc": "2026-10-15T00:00:00Z"}))
            now = dt.datetime(2026, 10, 15, 17, tzinfo=UTC)
            with patch.object(meteo, "ROOT", root), patch.object(meteo.urllib.request, "urlopen",
                                                                      side_effect=OSError("offline")):
                with self.assertRaisesRegex(RuntimeError, "seven-day limit"):
                    meteo.refresh_tle(sat, now, cfg, force=True)
        with self.assertRaises(ValueError):
            meteo.parse_tle("", 57166)

    def test_frequency_and_transmitter_state_are_not_claimed_as_confirmed(self):
        cfg = meteo.load_config()
        now = dt.datetime(2026, 10, 15, 17, tzinfo=UTC)
        with patch.object(meteo.urllib.request, "urlopen", side_effect=OSError("offline")):
            status = meteo.probe_transmitter_status(cfg, now)
        self.assertEqual(status["state"], "UNKNOWN")
        self.assertFalse(status["source_reachable"])
        self.assertEqual(status["checked_at_utc"], "2026-10-15T17:00:00.000Z")

    def test_dst_local_times_and_utc_are_both_reported(self):
        zone = ZoneInfo("America/New_York")
        winter = meteo._local("2026-01-15T06:30:00Z", zone)
        summer = meteo._local("2026-07-15T05:30:00Z", zone)
        self.assertIn("01:30:00 EST", winter)
        self.assertIn("01:30:00 EDT", summer)
        self.assertIn("2026-01-15T06:30:00Z", winter)
        self.assertIn("2026-07-15T05:30:00Z", summer)

    def test_expired_schedule_never_starts_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "schedule.json"
            path.write_text(json.dumps({"expires_utc": "2026-10-15T17:00:00Z", "passes": []}))
            with patch.object(meteo, "SCHEDULE", path):
                self.assertEqual(meteo.due(dt.datetime(2026, 10, 15, 18, tzinfo=UTC).timestamp()), [])

    def test_zero_cadu_or_missing_image_is_decode_failure_even_when_command_exits_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "frames.cadu").write_bytes(b"")
            log = "Viterbi sync\nDeframer sync\nValid frames: 10\n"
            result = meteo.evaluate_decode(0, out, log)
            self.assertEqual(result["status"], "failed")
            (out / "frames.cadu").write_bytes(b"data")
            (out / "image.png").write_bytes(b"image")
            result = meteo.evaluate_decode(0, out, log)
            self.assertEqual(result["status"], "decoded")
            (out / "frames.cadu").write_bytes(b"")
            self.assertEqual(meteo.evaluate_decode(0, out, log)["status"], "failed")

    def test_cb_channel_stays_removed_from_pmr_scanner(self):
        self.assertNotIn(rf_monitor.CB_USB, rf_monitor.scan_channels())
        self.assertEqual(len(rf_monitor.scan_channels()), 16)  # location-specific repeater slots omitted
        self.assertEqual(rf_monitor.LOCATION_REPEATER_OUTPUT_HZ, 0)

    def test_web_handover_stops_both_recorders_before_ack(self):
        from unittest.mock import MagicMock
        events = []
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.sendall.side_effect = lambda _: events.append("ack")
        server = MagicMock()
        server.accept.return_value = (connection, None)
        with patch.object(watcher, "set_meteo", side_effect=lambda _: events.append("meteo_stop")), \
             patch.object(watcher, "set_scanner", side_effect=lambda _: events.append("pmr_stop")), \
             patch.object(watcher, "reset_tuner_for_web", side_effect=lambda: events.append("reset")):
            watcher.release_for_web(server)
        self.assertEqual(events, ["meteo_stop", "pmr_stop", "reset", "ack"])

    def test_pmr_scanner_disabled_in_meteo_only_mode(self):
        self.assertFalse(watcher.SCAN_ENABLED)


if __name__ == "__main__":
    unittest.main()
