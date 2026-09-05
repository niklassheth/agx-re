exec(open('probe_exports.py').read().split('for field,val in ')[0])
producer=native.index(bytes.fromhex('49023c8149020010'))
for d in (4,16):
 for control in (0,1,0x20,0x21):
  data=bytearray(blob);code=bytearray(native)
  literal=bytearray(mov(d,0x3f600000));literal[2]|=control
  code[producer:producer+8]=literal;code[red+3]=d*2
  data[base:base+size]=code;data[fb:fb+fs]=fragment+bytes(fs-len(fragment))
  name=f'vtx-literal-r{d}-control{control:02x}';Path(name+'.archive').write_bytes(data)
  p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','8','--height','8','--no-fast-math'],capture_output=True,text=True,timeout=30)
  Path(name+'.log').write_text(p.stdout+p.stderr);print(name,p.returncode,[l for l in p.stdout.splitlines() if l.startswith('PIXEL 4 4') or l.startswith('STATUS')],flush=True)
  assert p.returncode==0,p.stdout+p.stderr
