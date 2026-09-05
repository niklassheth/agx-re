"""Test explicit color-store operand representations; never inspect launcher code."""
import json, struct, subprocess
from pathlib import Path
import agxparse
HERE=Path(__file__).resolve().parent
subprocess.run([str(HERE.parent/'EXP-M4-55-sqrt-sine-assist/tools/shdump'),'-o','native.bin','--render','--vertex','v_main','--fragment','f_main','probe.metal'],check=True)
blob=Path('native.bin').read_bytes()
for stage in ('vertex','fragment'):
    _, parts=agxparse.extract_agx(blob,stage)
    Path(stage+'.main.hex').write_text(parts['_agc.main'].hex()+'\n')
def mov(d,v):
    return bytes([((d&15)<<4)|12,128|(v&127),((d>>4)<<6)|2,(v>>24)&254,(v>>6)&30,(v>>9)&12,(v>>13)&255,(v>>21)&15])
def run(name,code):
    base,size=agxparse.locate_region(blob,'_agc.main','fragment')
    assert len(code)<=size,(len(code),size)
    data=bytearray(blob);data[base:base+size]=code+bytes(size-len(code))
    Path(name+'.bin').write_bytes(data)
    p=subprocess.run(['./agxrender','--archive',name+'.bin','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8'],capture_output=True,text=True,timeout=30)
    Path(name+'.log').write_text(p.stdout+p.stderr)
    print(name,p.returncode,[line for line in p.stdout.splitlines() if line.startswith('PIXEL 4 4') or line.startswith('STATUS')],flush=True)
    assert p.returncode==0,p.stdout+p.stderr
run('native-control',blob[slice(* (lambda b,n:(b,b+n))(*agxparse.locate_region(blob,'_agc.main','fragment')))])
for d in (0,2,16,31):
    for fmt,values in [('unorm8',[0xff4080bf]),('half',[0x38003a00,0x3c003400])]:
        code=b''.join(mov(d+i,v) for i,v in enumerate(values))
        code+=bytes.fromhex('8702540006008702540c0800')
        code+=bytes([0xe7,6,0x54,d*2,0,0,1,0x4e,0,0,0,0])
        code+=bytes.fromhex('0702540c02000e000000')
        run(f'color-{fmt}-r{d}',code)
