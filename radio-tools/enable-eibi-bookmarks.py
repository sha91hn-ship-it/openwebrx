#!/usr/bin/env python3
"""Enable automatic EIBI bookmarks and include language in their descriptions."""

import json
import shutil
from datetime import datetime
from pathlib import Path


settings_path = Path("/var/lib/openwebrx/settings.json")
eibi_path = Path("/usr/lib/python3/dist-packages/owrx/web/eibi.py")
stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

settings = json.loads(settings_path.read_text())
settings["eibi_bookmarks_range"] = 25000
new_settings = json.dumps(settings, indent=4, ensure_ascii=False) + "\n"

source = eibi_path.read_text()
needle = "        description = []\n"
language_block = (
    needle
    + '        if "lang" in b and b["lang"] not in ("", "-"):\n'
    + '            description += ["Language: " + b["lang"] + "."]\n'
)
if source.count(needle) != 1:
    raise SystemExit("Could not safely locate the EIBI description builder")
if 'description += ["Language: " + b["lang"] + "."]' not in source:
    source = source.replace(needle, language_block, 1)

settings_backup = settings_path.with_name(settings_path.name + ".bak-" + stamp)
eibi_backup = eibi_path.with_name(eibi_path.name + ".bak-" + stamp)
shutil.copy2(settings_path, settings_backup)
shutil.copy2(eibi_path, eibi_backup)
settings_path.write_text(new_settings)
eibi_path.write_text(source)
print(f"Enabled EIBI bookmarks up to 25000 km; backups: {settings_backup}, {eibi_backup}")
