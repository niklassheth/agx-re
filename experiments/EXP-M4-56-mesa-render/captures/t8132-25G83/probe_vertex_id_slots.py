import subprocess
from pathlib import Path
import agxparse
blob=Path('literal.bin').read_bytes();base,size=agxparse.locate_region(blob,'_agc.main','vertex');native=blob[base:base+size]
def mov(d,v):return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
fb,fs=agxparse.locate_region(blob,'_agc.main','fragment');frag=bytes.fromhex('2f0d54000302000210008702540006008702540c0800e70654000000014e000000000702540c02000e000000')
mesa=Path('mesa-vertex.bin').read_bytes();end=mesa.index(bytes.fromhex('570654'));source=mesa[end+3]//2
for kind in ['id']:
 for slot in range(7):
  d=8
  code=native.replace(bytes.fromhex('09012e0321000202'),b'',64)
  for lit in ('4c80233e0000000b4080','5c80233e000000064080','6c80233e0000000040a0'):code=code.replace(bytes.fromhex(lit),b'')
  for exp in ('5706550880404b00','5706540aa0404c00','5706560cc0404d00'):code=code.replace(bytes.fromhex(exp),b'')
  if kind=='x':head=mesa[:end];src=source
  elif kind=='constant':head=mov(16,0x3f600000);src=16
  else:
   head=bytes.fromhex('04dd100603000001' if kind=='id-zext' else '0cdd1006');src=0
   if kind=='id-copy':head=mesa[:14];src=16
   if kind=='id-mask':head=mesa[:32];src=18
   mask=0 if slot==0 else 1<<(slot-1)
   head+=bytes([0xa7,7|((mask&15)<<4),0x54|(mask>>4),40,3,src*4,0xac,0x20]);src=20
  # Multiply by one; preserves floating bits of the ID for raw observation.
  head+=mov(63,0x3f800000)+bytes([d*16+9,src*2+1,0x3d,127,0x41,0,0,0])
  head+=bytes([0x57,6,0x54,d*2,0x80,0x40,0,0])
  code=head+code
  data=bytearray(blob);data[base:base+size]=code+bytes(size-len(code));data[fb:fb+fs]=frag+bytes(fs-len(frag))
  name=f'vid-slot-{slot}';Path(name+'.archive').write_bytes(data)
  p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','literal.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
  Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
