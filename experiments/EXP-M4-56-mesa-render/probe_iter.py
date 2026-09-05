import subprocess
from pathlib import Path
import agxparse
blob=Path('large.bin').read_bytes()
base,size=agxparse.locate_region(blob,'_agc.main','fragment')
def run(name,code):
 data=bytearray(blob);data[base:base+size]=code+bytes(size-len(code));Path(name+'.archive').write_bytes(data)
 p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
 Path(name+'.log').write_text(p.stdout+p.stderr)
 print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
 assert p.returncode==0,p.stdout+p.stderr
run('constant-generated',Path('mesa-fragment-constant.bin').read_bytes())
for d in (0,1,2,16,31):
 for w in (False,True):
  code=bytes([0x2f,0x0d,0x54,d*2,3,0 if w else 2,4 if w else 0,2,0x10,0])
  code+=bytes.fromhex('8702540006008702540c0800')
  code+=bytes([0xe7,6,0x54,d*2,0,0,1,0x4e,0,0,0,0])
  code+=bytes.fromhex('0702540c02000e000000')
  run(f'iter-{"w" if w else "x"}-r{d}',code)
