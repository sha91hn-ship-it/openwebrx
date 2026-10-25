"""Add individual Band III DAB profiles, preserving existing radio settings."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from owrx.config.core import CoreConfig
from owrx.feature import FeatureDetector

CoreConfig.load()
assert FeatureDetector().is_available('dab'), 'DAB dependencies unavailable'
print('DAB/DAB+ dependencies: OK', flush=True)
path = Path('/var/lib/openwebrx/settings.json')
settings = json.loads(path.read_text())
profiles = settings['sdrs']['rtlsdr']['profiles']
channels = {}
for block, base in enumerate([174928,181936,188928,195936,202928,209936,216928,223936], 5):
    for i, letter in enumerate('ABCD'):
        channels[f'{block}{letter}'] = (base + i * 1712) * 1000
for letter, freq in zip('ABCDEF', [230784,232496,234208,235776,237488,239200]):
    channels['13' + letter] = freq * 1000
for channel, freq in channels.items():
    profiles['dab_' + channel.lower()] = {
        'name': f'DAB/DAB+ {channel} ({freq / 1000000:.3f} MHz)',
        'center_freq': freq, 'start_freq': freq,
        'samp_rate': 2048000, 'start_mod': 'dab',
        'rf_gain': 38.6, 'direct_sampling': 0, 'tuning_step': '1000',
    }
backup = str(path) + '.backup-dab-' + time.strftime('%Y%m%d-%H%M%S')
subprocess.run(['systemctl', 'stop', 'openwebrx'], check=True)
try:
    # Re-read after shutdown to preserve any settings saved during shutdown.
    current = json.loads(path.read_text())
    for key, value in profiles.items():
        if key.startswith('dab_'):
            current['sdrs']['rtlsdr']['profiles'][key] = value
    shutil.copy2(path, backup)
    stat = path.stat()
    temporary = path.with_suffix('.dab.tmp')
    temporary.write_text(json.dumps(current, indent=2, ensure_ascii=False) + '\n')
    os.chmod(temporary, stat.st_mode & 0o777)
    os.chown(temporary, stat.st_uid, stat.st_gid)
    os.replace(temporary, path)
finally:
    subprocess.run(['systemctl', 'start', 'openwebrx'], check=True)
print('Added', len(channels), 'DAB profiles; backup:', backup, flush=True)
subprocess.run(['systemctl', 'is-active', 'openwebrx'], check=True)
