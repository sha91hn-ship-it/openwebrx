# OpenWebRX receiver project

Anonymized project files for a single-SDR OpenWebRX setup, covering DAB audio fixes, profile access, and automated Meteor LRPT capture. This repository is public: actual machine settings, user records, bookmarks, recordings, API credentials, hardware serials, exact coordinates, and private network addresses are intentionally omitted. Account and home-directory placeholders are written as `user`; receiver place is written as `location`.

## Contents

- `openwebrx-profile-access/`: staged profile-access changes and guest/authenticated WebSocket checks.
- `radio-tools/`: DAB helpers and the Meteor SGP4 scheduler/capture program.
- `config/openwebrx-settings.example.json`: a minimal redacted example, not a copy of the live server settings.
- `radio-tools/meteo-config.example.json`: copy to `meteo-config.json`, then configure coordinates, timezone, storage, and SDR serial before using.

Install Python dependencies with `python3 -m pip install -r radio-tools/requirements.txt`.

The Meteor scheduler follows two satellites from CelesTrak TLEs and records only its locked top-five, non-overlapping pass targets. It requires the SDR to be idle; a running web receiver may prevent a capture. Transmission status is reported as UNKNOWN unless verified. The installed SatDump runtime on the source receiver is not included; its current ARM build is incompatible with that host.

## Validation

Run `python3 -m unittest -v test_meteo.py` from `radio-tools/` after installing the project dependencies.

## Current Meteor pass schedule

Receiver site is anonymized as `location`; times below are receiver-local, with timezone omitted. The list is refreshed from the hourly SGP4 plan. Forecasts become less certain farther from the TLE epoch. Last schedule calculation: `2026-10-25T12:46:12.456Z`. Satellite transmission state is UNKNOWN.

| Satellite | Frequency | Recording window (local) | Maximum (local) | Maximum elevation | TX state |
|---|---:|---|---|---:|---|
| Meteor-M2-3 | 137.900 MHz | 2026-10-27 09:27–2026-10-27 09:41 | 2026-10-27 09:34 | 89.7° | UNKNOWN |
| Meteor-M2-4 | 137.900 MHz | 2026-10-29 13:57–2026-10-29 14:12 | 2026-10-29 14:05 | 84.6° | UNKNOWN |
| Meteor-M2-4 | 137.900 MHz | 2026-11-01 03:08–2026-11-01 03:22 | 2026-11-01 03:15 | 86.7° | UNKNOWN |
| Meteor-M2-3 | 137.900 MHz | 2026-11-02 20:12–2026-11-02 20:26 | 2026-11-02 20:19 | 89.7° | UNKNOWN |
| Meteor-M2-4 | 137.900 MHz | 2026-11-03 13:49–2026-11-03 14:04 | 2026-11-03 13:57 | 83.5° | UNKNOWN |

When a new schedule is requested, update this section with the newly selected pass windows and calculation timestamp.
