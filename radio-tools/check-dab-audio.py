import os, time, threading
from pathlib import Path
import array, math
from pycsdr.modules import TcpSource, Buffer
from pycsdr.types import Format
import sys, importlib.util
if "--fixed" in sys.argv:
    for name, filename in [("csdr.module.toolbox", "toolbox.py"), ("csdr.chain.dablin", "dablin.py")]:
        spec = importlib.util.spec_from_file_location(name, "/home/user/radio-tools/dab-fix/" + filename)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
from csdr.chain.dablin import Dablin

port = None
for entry in Path('/proc').glob('[0-9]*/exe'):
    try:
        if os.readlink(entry) != '/usr/bin/rtl_connector': continue
        args = (entry.parent/'cmdline').read_bytes().decode().strip('\0').split('\0')
        if args[args.index('-f')+1] != '180064000': continue
        port = int(args[args.index('-p')+1])
    except (OSError, ValueError): pass
assert port, 'No live 5D receiver; no retuning performed'
source = TcpSource(port, Format.COMPLEX_FLOAT)
iq = Buffer(Format.COMPLEX_FLOAT, size=16777216)
chain = Dablin()
chain.setAudioServiceId(0xad5a)
output = Buffer(Format.FLOAT, size=1048576)
reader = output.getReader()
chunks = []
def consume():
    while True:
        data = reader.read()
        if not data: break
        chunks.append(bytes(data))
threading.Thread(target=consume, daemon=True).start()
chain.setWriter(output)
chain.setReader(iq.getReader())
source.setWriter(iq)
time.sleep(18)
raw = b''.join(chunks)
if raw:
    a = array.array("f", raw)
    finite = all(math.isfinite(x) for x in a)
    print('AUDIO', len(raw), 'bytes', len(a)/48000, 'seconds; finite', finite, flush=True)
    if finite: print("RMS", math.sqrt(sum(x*x for x in a)/len(a)), "peak", max(abs(x) for x in a), flush=True)
else: print('NO AUDIO received within 18 seconds', flush=True)
os._exit(0 if raw and finite else 1)
