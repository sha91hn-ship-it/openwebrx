import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile

for entry in Path('/proc').glob('[0-9]*/exe'):
    try:
        if os.readlink(entry)=='/usr/bin/rtl_connector':
            raise SystemExit('Browser receiver active; live test skipped')
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
with socket.socket(socket.AF_UNIX) as control:
    control.settimeout(25)
    control.connect('/run/pmr-idle-watch/control.sock')
    assert control.recv(16)==b'OK\n'
with tempfile.TemporaryDirectory(prefix='meteo-verification-', dir='/home/user/radio-tools') as folder:
    os.chmod(folder,0o777)
    code = "import sys;sys.path.insert(0,'/home/user/radio-tools');import meteo;from pathlib import Path;meteo.OUT=Path(sys.argv[1]);meteo.capture(4)"
    subprocess.run(['/usr/bin/python3','-c',code,folder],user='user',group='user',extra_groups=['plugdev'],check=True,timeout=20)
    recordings=list(Path(folder).glob('meteo_*.cu8'))
    assert len(recordings)==1
    raw=recordings[0].read_bytes()
    assert len(raw)>4_000_000, len(raw)
    assert len(set(raw[:65536]))>8
    meta=json.loads(recordings[0].with_suffix('.json').read_text())
    assert meta['status']=='completed'
    assert meta['format']=='cu8' and meta['sample_rate']==1024000
    print('PASS: live IQ at 1.024 MS/s,',len(raw),'bytes; prefix and metadata verified')
