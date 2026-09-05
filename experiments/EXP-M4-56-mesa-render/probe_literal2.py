import subprocess
from pathlib import Path
import agxparse
blob=Path('literal.bin').read_bytes();base,size=agxparse.locate_region(blob,'_agc.main','vertex');native=blob[base:base+size]
def mov(d,v): return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
fb,fs=agxparse.locate_region(blob,'_agc.main','fragment')
fragment=bytes.fromhex('2f0d54000302000210008702540006008702540c0800e70654000000014e000000000702540c02000e000000')
for variant,b6 in [('native',0x4b),('mode3',0x4b)]+[('mode2',v) for v in (0,8,0x40,0x48,0x4b,0x50,0x80,0xc0)]:
 code=bytearray(native)
 if variant=='mode2':code=code.replace(bytes.fromhex('4c80233e0000000b4080'),mov(4,0x3f600000))
 red=code.index(bytes.fromhex('5706550880404b00'))
 if variant!='native':code[red+1]=6;code[red+2]=0x54;code[red+6]=b6
 data=bytearray(blob);data[base:base+size]=code+bytes(size-len(code));data[fb:fb+fs]=fragment+bytes(fs-len(fragment))
 name=f'literal2-{variant}-{b6:02x}';Path(name+'.archive').write_bytes(data)
 p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','literal.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
 Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
 assert p.returncode==0,p.stdout+p.stderr
