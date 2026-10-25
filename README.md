# OpenWebRX receiver project

Anonymized project files for a single-SDR OpenWebRX setup, covering DAB audio fixes, profile access, and automated Meteor LRPT capture. This repository is public: actual machine settings, user records, bookmarks, recordings, API credentials, hardware serials, exact coordinates, and private network addresses are intentionally omitted. Account and home-directory placeholders are written as `user`; receiver place is written as `location`.

## Contents

- `openwebrx-profile-access/`: staged profile-access changes and guest/authenticated WebSocket checks.
- `radio-tools/`: DAB helpers and the Meteor SGP4 scheduler/capture program.
- `config/openwebrx-settings.example.json`: a minimal redacted example, not a copy of the live server settings.
- `radio-tools/meteo-config.example.json`: copy to `meteo-config.json`, then configure coordinates, timezone, storage, and SDR serial before using.

Install Python dependencies with `python3 -m pip install -r radio-tools/requirements.txt`.

The Meteor scheduler follows two satellites from CelesTrak TLEs and records only its locked top-five, non-overlapping pass targets. It requires the SDR to be idle; a running web receiver may prevent a capture. Transmission status is reported as UNKNOWN unless verified. The installed SatDump runtime on the source receiver is not included; its current ARM build is incompatible with that host.

## OpenWebRX-profilok frekvencia-lefedettsége

A lista a futó vevő konfigurált profiljait dokumentálja. A „vételi tartomány” az `center_freq ± samp_rate/2` alapján számolt névleges pillanatnyi IQ-sávszélesség, nem jogi frekvenciakiosztás vagy garantáltan használható analóg szűrősáv. A kezdő frekvencia és demodulációs mód a profil megnyitásakor beállított érték.

### Rövidhullámú, amatőr és egyéb profilok

Ezeket a profilokat rövidhullámú műsorszórók és hallgatók, engedéllyel működő rádióamatőrök, légi rádiós szolgálatok, illetve ISM/telemetriai eszközök vételére állították be.

| Profil | Kezdő hangolás | Névleges vételi tartomány | Mód | Mintavétel |
|---|---:|---:|:---:|---:|
| 160 m | 1.800 MHz | 0.988–2.012 MHz | LSB | 1.024 Msps |
| 80 m | 3.700 MHz | 2.988–4.012 MHz | LSB | 1.024 Msps |
| 40 m | 7.300 MHz | 6.988–8.012 MHz | LSB | 1.024 Msps |
| 30 m amatőr | 10.136 MHz | 9.613–10.637 MHz | USB | 1.024 Msps |
| 20 m amatőr | 14.200 MHz | 13.663–14.687 MHz | USB | 1.024 Msps |
| 15 m amatőr | 21.285 MHz | 20.713–21.737 MHz | USB | 1.024 Msps |
| 10 m + CB | 27.500 MHz | 26.976–29.024 MHz | AM | 2.048 Msps |
| 41 m rövidhullámú műsorszórás | 7.320 MHz | 6.888–7.912 MHz | AM | 1.024 Msps |
| 49 m rövidhullámú műsorszórás | 6.070 MHz | 5.538–6.562 MHz | AM | 1.024 Msps |
| 31 m rövidhullámú műsorszórás | 9.700 MHz | 9.138–10.162 MHz | AM | 1.024 Msps |
| 22 m rövidhullámú műsorszórás | 13.700 MHz | 13.208–14.232 MHz | AM | 1.024 Msps |
| 25 m rövidhullámú műsorszórás | 12.000 MHz | 11.338–12.362 MHz | AM | 1.024 Msps |
| 19 m rövidhullámú műsorszórás | 15.500 MHz | 14.938–15.962 MHz | AM | 1.024 Msps |
| 16 m rövidhullámú műsorszórás | 17.700 MHz | 17.178–18.202 MHz | AM | 1.024 Msps |
| AM középhullám | 1.200 MHz | 0.488–1.512 MHz | AM | 1.024 Msps |
| 433 MHz ISM – időjárás-állomások | 433.920 MHz | 432.920–434.920 MHz | ISM | 2.000 Msps |
| PMR446 | 446.00625 MHz | 445.588–446.612 MHz | NFM | 1.024 Msps |
| 2 m amatőr | 145.7125 MHz | 143.976–146.024 MHz | NFM | 2.048 Msps |
| 70 cm amatőr átjátszók | 439.275 MHz | 437.600–440.000 MHz | NFM | 2.400 Msps |
| ADS-B | 1090.000 MHz | 1088.800–1091.200 MHz | ADS-B | 2.400 Msps |
| Légi sáv – profil A | 125.500 MHz | 124.300–126.700 MHz | AM | 2.400 Msps |
| Légi sáv – profil B | 129.500 MHz | 128.400–130.800 MHz | AM | 2.400 Msps |
| Légi sáv – profil C | 131.250 MHz | 130.300–132.700 MHz | AM | 2.400 Msps |
| Légi sáv – profil D | 134.585 MHz | 133.400–135.800 MHz | AM | 2.400 Msps |
| FM műsorszórás 87.5–89.5 MHz | 88.100 MHz | 87.300–89.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 89.5–91.5 MHz | 90.100 MHz | 89.300–91.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 91.5–93.5 MHz | 92.100 MHz | 91.300–93.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 93.5–95.5 MHz | 94.100 MHz | 93.300–95.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 95.5–97.5 MHz | 96.100 MHz | 95.300–97.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 97.5–99.5 MHz | 98.100 MHz | 97.300–99.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 99.5–101.5 MHz | 100.100 MHz | 99.300–101.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 101.5–103.5 MHz | 102.100 MHz | 101.300–103.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 103.5–105.5 MHz | 104.100 MHz | 103.300–105.700 MHz | WFM | 2.400 Msps |
| FM műsorszórás 105.5–108 MHz | 106.100 MHz | 105.500–107.900 MHz | WFM | 2.400 Msps |
| Meteor LRPT – M2-3/M2-4 | 137.900 MHz | 136.988–138.012 MHz | WFM | 1.024 Msps |

A 10 m + CB profil tényleges mintavételi ablaka 26.976–29.024 MHz, ezért nem fedi le sem a teljes CEPT CB-sávot, sem a teljes 10 m amatőrsávot. A CB CH 01 (26.965 MHz), valamint a 29.024 MHz fölötti 10 m-es pontok ezen a profilon kívül esnek.

### DAB/DAB+ profilok

A DAB/DAB+ digitális földfelszíni rádió multiplexeit a műsorszórók üzemeltetik; a hallgatók a csatornablokkokon több rádióműsort vehetnek. Mindegyik profil 2.048 Msps mintavételű, DAB demodulációjú, a kezdő hangolás a blokk középfrekvenciája. A vételi tartomány oszlop a konfigurált mintavételi ablakot mutatja.

| Profil | Kezdő hangolás | Névleges vételi tartomány | Mód | Mintavétel |
|---|---:|---:|:---:|---:|
| DAB/DAB+ 5A | 174.928 MHz | 173.904–175.952 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 5B | 176.640 MHz | 175.616–177.664 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 5C | 178.352 MHz | 177.328–179.376 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 5D | 180.064 MHz | 179.040–181.088 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 6A | 181.936 MHz | 180.912–182.960 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 6B | 183.648 MHz | 182.624–184.672 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 6C | 185.360 MHz | 184.336–186.384 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 6D | 187.072 MHz | 186.048–188.096 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 7A | 188.928 MHz | 187.904–189.952 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 7B | 190.640 MHz | 189.616–191.664 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 7C | 192.352 MHz | 191.328–193.376 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 7D | 194.064 MHz | 193.040–195.088 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 8A | 195.936 MHz | 194.912–196.960 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 8B | 197.648 MHz | 196.624–198.672 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 8C | 199.360 MHz | 198.336–200.384 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 8D | 201.072 MHz | 200.048–202.096 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 9A | 202.928 MHz | 201.904–203.952 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 9B | 204.640 MHz | 203.616–205.664 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 9C | 206.352 MHz | 205.328–207.376 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 9D | 208.064 MHz | 207.040–209.088 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 10A | 209.936 MHz | 208.912–210.960 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 10B | 211.648 MHz | 210.624–212.672 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 10C | 213.360 MHz | 212.336–214.384 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 10D | 215.072 MHz | 214.048–216.096 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 11A | 216.928 MHz | 215.904–217.952 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 11B | 218.640 MHz | 217.616–219.664 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 11C | 220.352 MHz | 219.328–221.376 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 11D | 222.064 MHz | 221.040–223.088 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 12A | 223.936 MHz | 222.912–224.960 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 12B | 225.648 MHz | 224.624–226.672 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 12C | 227.360 MHz | 226.336–228.384 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 12D | 229.072 MHz | 228.048–230.096 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13A | 230.784 MHz | 229.760–231.808 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13B | 232.496 MHz | 231.472–233.520 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13C | 234.208 MHz | 233.184–235.232 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13D | 235.776 MHz | 234.752–236.800 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13E | 237.488 MHz | 236.464–238.512 MHz | DAB | 2.048 Msps |
| DAB/DAB+ 13F | 239.200 MHz | 238.176–240.224 MHz | DAB | 2.048 Msps |

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
