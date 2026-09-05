import subprocess
from pathlib import Path
import agxparse
subprocess.run(['../EXP-M4-55-sqrt-sine-assist/tools/shdump','-o','large.bin','--render','--vertex','v_main','--fragment','f_main','--no-fast-math','probe.metal'],check=True)
blob=Path('large.bin').read_bytes()
for stages in [('vertex',),('fragment',),('vertex','fragment')]:
    data=bytearray(blob)
    for stage in stages:
        base,size=agxparse.locate_region(blob,'_agc.main',stage)
        code=Path('mesa-'+stage+'.bin').read_bytes()
        print(stage, 'region',size,'generated',len(code),flush=True)
        assert len(code)<=size
        data[base:base+size]=code+bytes(size-len(code))
    name='mesa-'+'-'.join(stages)
    Path(name+'.archive').write_bytes(data)
    p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','16','--height','16','--no-fast-math'],capture_output=True,text=True,timeout=40)
    Path(name+'.log').write_text(p.stdout+p.stderr)
    print(name,p.returncode,[line for line in p.stdout.splitlines() if line.startswith('PIXEL 8 8') or line.startswith('STATUS')],flush=True)
    assert p.returncode==0,p.stdout+p.stderr
