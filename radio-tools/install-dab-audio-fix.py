import ast, pathlib, shutil, subprocess, time
base=pathlib.Path('/home/user/radio-tools/dab-fix')
files=[(base/'toolbox.py',pathlib.Path('/usr/lib/python3/dist-packages/csdr/module/toolbox.py')),(base/'dablin.py',pathlib.Path('/usr/lib/python3/dist-packages/csdr/chain/dablin.py'))]
for source,target in files: ast.parse(source.read_text())
stamp=time.strftime('%Y%m%d-%H%M%S')
for source,target in files:
 backup=str(target)+'.backup-dab-audio-'+stamp
 shutil.copy2(target,backup)
 target.write_bytes(source.read_bytes())
 print('Installed',target,'backup',backup,flush=True)
subprocess.run(['systemctl','restart','openwebrx'],check=True)
subprocess.run(['systemctl','is-active','openwebrx'],check=True)
