"""Apply the local OpenWebRX profile login extension and selected profile flags."""

import json
import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PACKAGE = Path("/usr/lib/python3/dist-packages/owrx")
SETTINGS = Path("/var/lib/openwebrx/settings.json")
FILES = (
    "source/__init__.py",
    "controllers/websocket.py",
    "connection.py",
    "controllers/status.py",
)
FM_PROFILES = [f"fm_{frequency}" for frequency in range(88, 108, 2)]
AIRBAND_PROFILES = [
    "airband_125500",
    "airband_129600",
    "airband_131500",
    "airband_134600",
]
PUBLIC_PROFILES = set(FM_PROFILES + AIRBAND_PROFILES)
PROFILE_ORDER_ANCHOR = "30m_amateur"


def main():
    originals = ROOT / "originals"
    originals.mkdir(exist_ok=True)
    for relative in FILES:
        source = PACKAGE / relative
        backup = originals / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(source, backup)
        staged = ROOT / "staging" / relative
        compile(staged.read_bytes(), str(staged), "exec")

    data = json.loads(SETTINGS.read_text())
    profiles = data["sdrs"]["rtlsdr"]["profiles"]
    missing = PUBLIC_PROFILES - profiles.keys()
    if missing:
        raise RuntimeError(f"Missing target profiles: {sorted(missing)}")

    settings_backup = SETTINGS.with_name("settings.json.backup-profile-access")
    if not settings_backup.exists():
        shutil.copy2(SETTINGS, settings_backup)

    for relative in FILES:
        shutil.copy2(ROOT / "staging" / relative, PACKAGE / relative)

    missing_fm = set(FM_PROFILES) - profiles.keys()
    if missing_fm or PROFILE_ORDER_ANCHOR not in profiles:
        raise RuntimeError(f"Missing FM profiles or order anchor: {sorted(missing_fm)}")
    for profile_id in FM_PROFILES:
        profiles[profile_id].pop("login_required", None)
    for profile_id in AIRBAND_PROFILES:
        profiles[profile_id].pop("login_required", None)
    ordered = [(key, value) for key, value in profiles.items() if key not in FM_PROFILES]
    anchor_index = next(i for i, (key, _) in enumerate(ordered) if key == PROFILE_ORDER_ANCHOR) + 1
    ordered[anchor_index:anchor_index] = [(key, profiles[key]) for key in FM_PROFILES]
    data["sdrs"]["rtlsdr"]["profiles"] = dict(ordered)

    temporary = SETTINGS.with_name("settings.json.profile-access-new")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        stat = SETTINGS.stat()
        os.chown(temporary, stat.st_uid, stat.st_gid)
        os.chmod(temporary, stat.st_mode)
        os.replace(temporary, SETTINGS)
    finally:
        temporary.unlink(missing_ok=True)

    subprocess.run(["systemctl", "restart", "openwebrx"], check=True)
    print(f"Public access enabled for {len(PUBLIC_PROFILES)} FM/Airband profiles; OpenWebRX restarted.")


if __name__ == "__main__":
    main()
