import subprocess
from pathlib import Path
import agxparse
blob=Path('literal.bin').read_bytes();base,size=agxparse.locate_region(blob,'_agc.main','vertex');native=blob[base:base+size]
def mov(d,v): return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
fb,fs=agxparse.locate_region(blob,'_agc.main','fragment')
fragment=bytes.fromhex('2f0d54000302000210008702540006008702540c0800e70654000000014e000000000702540c02000e000000')
for kind in ['modifier','same','same23','alu','alu-ext','alu-ext40','alu-ext44','alu-ext20']:
 code=bytearray(native.replace(bytes.fromhex('09012e0321000202'),b'',4))
 literal=bytearray(mov(4,0x3f600000))
 if kind=='modifier':literal[2]|=32
 if kind in ('same','same23'):literal[2]|=1 if kind=='same' else 33;literal+=bytes.fromhex('4080')
 if kind.startswith('alu'):
  # ordinary independently encoded fadd r4 = r4 + r7 (zero)
  literal+=mov(7,0)
  alu=bytearray.fromhex('49093c0f0000')
  if kind!='alu':
   alu[4]|=1;alu+=bytes.fromhex('0010')
   if kind=='alu-ext40':alu[4]|=0x40
   if kind=='alu-ext44':alu[4]|=0x44
   if kind=='alu-ext20':alu[4]|=0x20
  literal+=alu
 code=code.replace(bytes.fromhex('4c80233e0000000b4080'),literal)
 red=code.index(bytes.fromhex('5706550880404b00'));code[red+1]=6;code[red+2]=0x54
 data=bytearray(blob);data[base:base+size]=code+bytes(size-len(code));data[fb:fb+fs]=fragment+bytes(fs-len(fragment))
 name='publish-'+kind;Path(name+'.archive').write_bytes(data)
 p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','literal.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
 Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
