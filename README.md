# OpenWebRX receiver project

Anonymized project files for a single-SDR OpenWebRX setup, covering DAB audio fixes, profile access, and automated Meteor LRPT capture. This repository is public: actual machine settings, user records, bookmarks, recordings, API credentials, hardware serials, exact coordinates, and private network addresses are intentionally omitted. Account and home-directory placeholders are written as `user`; receiver place is written as `location`.

## Contents

- `openwebrx-profile-access/`: staged profile-access changes and guest/authenticated WebSocket checks.
- `radio-tools/`: DAB helpers and the Meteor SGP4 scheduler/capture program.
- `config/openwebrx-settings.example.json`: a minimal redacted example, not a copy of the live server settings.
- `radio-tools/meteo-config.example.json`: copy to `meteo-config.json`, then configure coordinates, timezone, storage, and SDR serial before using.

Install Python dependencies with `python3 -m pip install -r radio-tools/requirements.txt`.

The Meteor scheduler follows two satellites from CelesTrak TLEs and records only its locked top-five, non-overlapping pass targets. It requires the SDR to be idle; a running web receiver may prevent a capture. Transmission status is reported as UNKNOWN unless verified. The installed SatDump runtime on the source receiver is not included; its current ARM build is incompatible with that host.

## CB, 11 m freeband és 10 m amatőrsáv – frekvencialeltár

A táblázatok a vevőben beállított bookmarkokat sorolják fel. A mód a bookmark demodulációs alapbeállítása, vételre szolgál; önmagában nem jelent adási jogosultságot.

### CB (CEPT, 26.960–27.410 MHz)

A CB-t Európában magánszemélyek és járművezetők használják rövid hatótávú, helyi vagy mobil kommunikációra, az adott ország szabályai szerint. A CEPT kiosztás 40 csatornából áll. A csatornafrekvenciák az [Ofcom CEPT táblázatából](https://www.ofcom.org.uk/__data/assets/pdf_file/0025/72169/citizen-band-radio.pdf) származnak.

| Csatorna | Frekvencia | Vevőmód | Megjegyzés |
|---:|---:|:---:|---|
| 01 | 26.965 MHz | USB | CEPT |
| 02 | 26.975 MHz | USB | CEPT |
| 03 | 26.985 MHz | USB | CEPT |
| 04 | 27.005 MHz | USB | CEPT |
| 05 | 27.015 MHz | USB | CEPT |
| 06 | 27.025 MHz | AM | „Super Bowl” – észak-amerikai, nem hivatalos konvenció |
| 07 | 27.035 MHz | USB | CEPT |
| 08 | 27.055 MHz | USB | CEPT |
| 09 | 27.065 MHz | AM | Vészhívó konvenció; országonként eltérhet |
| 10 | 27.075 MHz | USB | CEPT |
| 11 | 27.085 MHz | AM | Hívócsatorna-konvenció egyes régiókban |
| 12 | 27.105 MHz | USB | CEPT |
| 13 | 27.115 MHz | USB | CEPT |
| 14 | 27.125 MHz | USB | CEPT |
| 15 | 27.135 MHz | USB | CEPT |
| 16 | 27.155 MHz | LSB | Egyes régiók LSB hívókonvenciója |
| 17 | 27.165 MHz | USB | CEPT |
| 18 | 27.175 MHz | USB | CEPT |
| 19 | 27.185 MHz | AM | Közúti/trucker konvenció; régiónként változhat |
| 20 | 27.205 MHz | USB | CEPT |
| 21 | 27.215 MHz | USB | CEPT |
| 22 | 27.225 MHz | USB | CEPT |
| 23 | 27.255 MHz | USB | CEPT |
| 24 | 27.235 MHz | USB | CEPT; a számozás nem frekvenciasorrendű |
| 25 | 27.245 MHz | USB | CEPT |
| 26 | 27.265 MHz | USB | CEPT |
| 27 | 27.275 MHz | USB | CEPT |
| 28 | 27.285 MHz | USB | CEPT |
| 29 | 27.295 MHz | USB | CEPT |
| 30 | 27.305 MHz | USB | CEPT |
| 31 | 27.315 MHz | USB | CEPT |
| 32 | 27.325 MHz | USB | CEPT |
| 33 | 27.335 MHz | USB | CEPT |
| 34 | 27.345 MHz | USB | CEPT |
| 35 | 27.355 MHz | LSB | LSB hívókonvenció főként Ausztrália/Oceánia térségében |
| 36 | 27.365 MHz | USB | CEPT |
| 37 | 27.375 MHz | USB | CEPT |
| 38 | 27.385 MHz | LSB | SSB hívókonvenció főként Észak-Amerikában |
| 39 | 27.395 MHz | USB | CEPT |
| 40 | 27.405 MHz | USB | CEPT |

### 11 m freeband (nem hivatalos CB- vagy amatőrcsatornák)

Ezek közösségileg használt DX-hívóhelyek a CEPT 40 csatornás CB-kiosztásán kívül. Freeband használatuk régiónként eltérő; a bookmarkok vételi célúak.

| Frekvencia | Vevőmód | Megjegyzés |
|---:|:---:|---|
| 27.455 MHz | USB | Közösségi, főként spanyol nyelvű DX-hívókonvenció |
| 27.555 MHz | USB | Nemzetközi 11 m SSB DX-hívókonvenció |

### 10 m amatőrsáv (28.000–29.700 MHz)

Ezt a sávot engedéllyel rendelkező rádióamatőrök használják. A 28 MHz-es sávon CW, digitális üzemmódok, terjedési beaconök, USB/SSB, képátvitel, FM és műholdas összeköttetések találhatók. Az IARU Region 1 terv használati ajánlásokat és szegmenseket ad meg; a közösségi frekvenciakonvenciók külön jelöltek. Forrás: [IARU Region 1 HF band plan](https://www.iaru-r1.org/wp-content/uploads/2021/06/hf_r1_bandplan.pdf).

| Bookmark / használat | Frekvencia | Vevőmód | Jelleg |
|---|---:|:---:|---|
| CW szegmens kezdete | 28.000 MHz | CW | IARU R1 sávterv |
| QRS CW | 28.055 MHz | CW | IARU R1 aktivitási pont |
| CW QRP | 28.060 MHz | CW | IARU R1 aktivitási pont |
| Keskenysávú digitális szegmens kezdete | 28.070 MHz | USB | IARU R1 sávterv |
| FT8 | 28.074 MHz | USB | Közösségi digitális frekvenciakonvenció |
| JS8 | 28.078 MHz | USB | Közösségi digitális frekvenciakonvenció |
| RTTY | 28.080 MHz | USB | Közösségi digitális frekvenciakonvenció |
| WSPR | 28.1246 MHz | USB | Közösségi aktivitási frekvencia |
| FT4 | 28.180 MHz | USB | Közösségi digitális frekvenciakonvenció |
| IBP globális beacon | 28.200 MHz | CW | IARU R1 / International Beacon Project |
| Beacon szegmens kezdete | 28.225 MHz | CW | IARU R1; tényleges beacon-mód változhat |
| Digital Voice aktivitási pont | 28.330 MHz | USB | IARU R1 |
| SSB QRP | 28.360 MHz | USB | IARU R1 aktivitási pont |
| SSB hívó | 28.400 MHz | USB | Közösségi, nem külön IARU R1 pont |
| SSB hívó/DX | 28.500 MHz | USB | Közösségi hívókonvenció |
| SSTV képátvitel | 28.680 MHz | SSTV | IARU R1 aktivitási pont |
| FM simplex CH 01 | 29.100 MHz | NFM | IARU R1, 10 kHz-es csatornarács |
| FM simplex CH 02 | 29.110 MHz | NFM | IARU R1 |
| FM simplex CH 03 | 29.120 MHz | NFM | IARU R1 |
| FM simplex CH 04 | 29.130 MHz | NFM | IARU R1 |
| FM simplex CH 05 | 29.140 MHz | NFM | IARU R1 |
| FM simplex CH 06 | 29.150 MHz | NFM | IARU R1 |
| FM simplex CH 07 | 29.160 MHz | NFM | IARU R1 |
| FM simplex CH 08 | 29.170 MHz | NFM | IARU R1 |
| FM simplex CH 09 | 29.180 MHz | NFM | IARU R1 |
| FM simplex CH 10 | 29.190 MHz | NFM | IARU R1 |
| Digitális FM szegmens kezdete | 29.200 MHz | NFM | IARU R1 |
| Műholdas összeköttetési szegmens kezdete | 29.300 MHz | USB | IARU R1; a konkrét műhold és mód változó |
| Műhold/átjátszó védősáv | 29.510 MHz | NFM | IARU R1 guard channel |
| RH1 átjátszó bemenet | 29.520 MHz | NFM | IARU R1; kimenet 29.620 MHz |
| RH2 átjátszó bemenet | 29.530 MHz | NFM | IARU R1; kimenet 29.630 MHz |
| RH3 átjátszó bemenet | 29.540 MHz | NFM | IARU R1; kimenet 29.640 MHz |
| RH4 átjátszó bemenet | 29.550 MHz | NFM | IARU R1; kimenet 29.650 MHz |
| RH5 átjátszó bemenet | 29.560 MHz | NFM | IARU R1; kimenet 29.660 MHz |
| RH6 átjátszó bemenet | 29.570 MHz | NFM | IARU R1; kimenet 29.670 MHz |
| RH7 átjátszó bemenet | 29.580 MHz | NFM | IARU R1; kimenet 29.680 MHz |
| RH8 átjátszó bemenet | 29.590 MHz | NFM | IARU R1; kimenet 29.690 MHz |
| FM simplex hívócsatorna | 29.600 MHz | NFM | IARU R1 |
| Simplex parrot/repeater | 29.610 MHz | NFM | IARU R1 |
| RH1 átjátszó kimenet | 29.620 MHz | NFM | IARU R1; bemenet 29.520 MHz |
| RH2 átjátszó kimenet | 29.630 MHz | NFM | IARU R1; bemenet 29.530 MHz |
| RH3 átjátszó kimenet | 29.640 MHz | NFM | IARU R1; bemenet 29.540 MHz |
| RH4 átjátszó kimenet | 29.650 MHz | NFM | IARU R1; bemenet 29.550 MHz |
| RH5 átjátszó kimenet | 29.660 MHz | NFM | IARU R1; bemenet 29.560 MHz |
| RH6 átjátszó kimenet | 29.670 MHz | NFM | IARU R1; bemenet 29.570 MHz |
| RH7 átjátszó kimenet | 29.680 MHz | NFM | IARU R1; bemenet 29.580 MHz |
| RH8 átjátszó kimenet | 29.690 MHz | NFM | IARU R1; bemenet 29.590 MHz |

A 10 m sávtervi segédpontok és a közösségi használatok nem minden országban jelentenek önálló csatornakijelölést. A tényleges adási feltételeket mindig a helyi szabályozás és az egyéni rádióamatőr engedély határozza meg.

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
