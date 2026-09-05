import subprocess
from pathlib import Path
import agxparse
blob=Path('large.bin').read_bytes()
def mov(d,v): return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
for hint in (0,0x48):
 for tag in (0,4):
  d=0
  code=Path('mesa-vertex.bin').read_bytes(); new=bytearray();last=0
  for i in range(len(code)-7):
   if code[i:i+3]==bytes.fromhex('570654'):
    new+=code[last:i];s=code[i+3]//2;d=code[i+4]>>5
    new+=mov(63,0x3f800000)+bytes([d*16+9,s*2+1,0x35,127,0x41,0,0,tag<<2])
    export=bytearray(code[i:i+8]);export[3]=d*2;export[6]=hint+d if hint else 0;new+=export;last=i+8
  new+=code[last:]
  data=bytearray(blob)
  for stage,body in [('vertex',new),('fragment',Path('mesa-fragment.bin').read_bytes())]:
   base,size=agxparse.locate_region(blob,'_agc.main',stage);data[base:base+size]=body+bytes(size-len(body))
  name=f'mesapub-unique-{hint}-{tag}';Path(name+'.archive').write_bytes(data)
  p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','16','--height','16','--no-fast-math'],capture_output=True,text=True,timeout=30)
  Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 8 8') or l.startswith('STATUS')],flush=True)
