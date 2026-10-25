"""Check live RTL-SDR sampling at the DAB rate without disrupting web users."""
import os
from pathlib import Path
import socket
import subprocess
import tempfile

for entry in Path('/proc').glob('[0-9]*/exe'):
    try:
        if os.readlink(entry) == '/usr/bin/rtl_connector':
            raise SystemExit('Web receiver in use; hardware capture skipped')
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
with socket.socket(socket.AF_UNIX) as control:
    control.settimeout(25)
    control.connect('/run/pmr-idle-watch/control.sock')
    assert control.recv(16) == b'OK\n'
with tempfile.TemporaryDirectory(prefix='dab-hardware-') as directory:
    target = Path(directory) / 'samples.iq'
    result = subprocess.run(
        ['rtl_sdr', '-d', '0', '-f', '195936000', '-s', '2048000',
         '-g', '38.6', '-n', '4096000', str(target)],
        capture_output=True, timeout=20)
    print(result.stderr.decode(), flush=True)
    assert result.returncode == 0, 'RTL-SDR acquisition failed'
    data = target.read_bytes()
    assert len(data) >= 8192000, f'Short capture: {len(data)} bytes'
    assert len(set(data[:65536])) > 8, 'IQ samples appear constant'
    print('Verified live DAB-rate IQ:', len(data), 'bytes at 2.048 MS/s')
    print('This proves tuner sampling, not DAB station reception or antenna suitability.')
