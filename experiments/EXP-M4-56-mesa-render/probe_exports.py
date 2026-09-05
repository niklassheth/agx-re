import subprocess
from pathlib import Path
import agxparse
blob=Path('large.bin').read_bytes();base,size=agxparse.locate_region(blob,'_agc.main','vertex');native=blob[base:base+size]
def mov(d,v): return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
# This FMA implements the explicit repeated fma in probe.metal. Replace one
# iteration with a literal; the remaining iterations leave geometry near its
# original location. No launcher code is examined or changed.
fma=native.index(bytes.fromhex('19032e0321000202'))
exports=[i for i in range(len(native)-7) if native[i]==0x57 and native[i+2] in (0x54,0x55,0x56) and native[i+5]==0x40]
assert len(exports)==7, exports
red=exports[4]
fb,fs=agxparse.locate_region(blob,'_agc.main','fragment')
# Independently expose the first color coefficient as raw bits through RGBA8.
fragment=bytes.fromhex('2f0d54000302000210008702540006008702540c0800e70654000000014e000000000702540c02000e000000')
for field,val in [(3,32),(6,0x50),(3,0),(6,0x48),(6,0),(2,0x54)]:
 data=bytearray(blob);code=bytearray(native);code[fma:fma+8]=mov(16,0x3f600000);code[red+field]=val
 data[base:base+size]=code;data[fb:fb+fs]=fragment+bytes(fs-len(fragment))
 name=f'export-b{field}-{val:02x}';Path(name+'.archive').write_bytes(data)
 p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
 Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
 assert p.returncode==0,p.stdout+p.stderr
