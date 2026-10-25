#!/usr/bin/env python3
"""Install Meteor-only scheduling without changing OpenWebRX settings."""
import ast
from datetime import datetime
from pathlib import Path
import shutil
import subprocess

BASE = Path(__file__).resolve().parent
SYSTEMD = Path('/etc/systemd/system')
WATCHER = Path('/usr/local/sbin/pmr_idle_watch.py')

for name in ('meteo.py', 'pmr_idle_watch.py'):
    ast.parse((BASE / name).read_text())

def run(*args, check=True):
    subprocess.run(args, check=check)

if subprocess.run(['systemctl', 'is-active', '--quiet', 'meteo-capture']).returncode == 0:
    raise SystemExit('A Meteor capture is active; wait for its pass to finish before installing.')

backup = Path('/var/backups') / ('meteo-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
backup.mkdir(parents=True)
for path in [WATCHER, *(SYSTEMD / name for name in (
        'pmr-idle-watch.service', 'meteo-plan.service', 'meteo-plan.timer', 'meteo-capture.service'))]:
    if path.exists():
        shutil.copy2(path, backup / path.name)

# Stop all unattended tuner owners while swapping their code and unit files.
run('systemctl', 'stop', 'pmr-idle-watch', 'pmr-scan', 'meteo-plan.timer', 'meteo-capture', check=False)
shutil.copy2(BASE / 'pmr_idle_watch.py', WATCHER)
for name in ('meteo-plan.service', 'meteo-plan.timer', 'meteo-capture.service'):
    shutil.copy2(BASE / name, SYSTEMD / name)
shutil.copy2(BASE / 'pmr-idle-watch.service', SYSTEMD / 'pmr-idle-watch.service')
run('systemctl', 'daemon-reload')
run('systemctl', 'disable', '--now', 'pmr-scan.service', check=False)
run('systemctl', 'enable', '--now', 'meteo-plan.timer')
run('systemctl', 'enable', '--now', 'pmr-idle-watch.service')
print(f'Installed Meteor-only scheduler; previous files backed up in {backup}')
