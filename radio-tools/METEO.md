# Meteor LRPT automatic recorder

The recorder tracks Meteor-M2-3 (NORAD 57166) and Meteor-M2-4 (59051) over
location (coordinates redacted), in `UTC`. Internal timestamps
are UTC; plans also show local time. Edit `meteo-config.json` to change the
station or capture thresholds.

`meteo-plan.timer` refreshes CelesTrak TLEs at least every six hours and
recomputes the next 14 days hourly using SGP4. It logs AOS, TCA, LOS, azimuth,
maximum elevation, frequency and transmitter-state source. Only the five
highest-elevation, non-overlapping passes at or above 30° are retained as
recording targets. The selected targets stay fixed while hourly TLE updates
refine their predicted times. IQ capture spans the rising and setting 10°
crossings with two-minute margins. Unverified transmitter state stays
`UNKNOWN`.

The one RTL-SDR Blog V4 is tuned to the selected satellite frequency (currently
137.900 MHz for each, configurable), at 1.024 Msps and manual 38.6 dB gain.
Files are raw interleaved unsigned 8-bit I/Q (`cu8`), with zero frequency shift.
An installed-device log previously confirmed the RTL-SDR tool's CU8 stream,
sample rate and gain. Capture metadata checks expected bytes, disk space and
stream growth. Captures include JSON metadata and logs; spectrum analysis is
attempted after normal completion. Interrupted partial captures are retained.

The PMR scanner is disabled in the idle watcher, and `pmr-scan.service` is
disabled by the installer. The watcher still pauses a Meteor capture when a
web receiver needs the shared SDR. Existing OpenWebRX settings and bookmarks
are not changed by the Meteor installer. Old recordings are never deleted.

SatDump processing is held as unavailable: the installed AArch64 binary exits
with SIGILL on this Raspberry Pi. The scheduler must not report a capture as
decoded unless synchronization, nonzero valid CADU frames, nonempty CADU, and
an output image are all present. A compatible SatDump runtime remains needed
to produce images automatically.

Output: `/home/user/radio-recordings/meteo/meteo_*.cu8` plus JSON and log
sidecars. The 36 GiB storage cap is a recording limit, not an automatic cleanup
policy. The recorder keeps a 2 GiB free-space reserve plus the space required
for the next capture. Run tests with `python3 -m unittest -v test_meteo.py test_scan_schedule.py`.
