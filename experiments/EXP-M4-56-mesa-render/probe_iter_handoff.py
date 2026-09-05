exec(open('probe_iter.py').read().split("run('constant-generated'")[0])
for slot in (0,1):
 for mode in (0,4):
  for dep in (None,0,2):
   d=16
   code=bytes([0x2f,0x0d,0x54,d*2,3,slot*2,mode,2,0x10,0])
   out=d
   if dep is not None:
    code+=bytes([0xaf,0,0x54|dep,(d+1)*2,3,d*4,0,0x48,0x20,0]);out=d+1
   code+=bytes.fromhex('8702540006008702540c0800')
   code+=bytes([0xe7,6,0x54,out*2,0,0,1,0x4e,0,0,0,0])
   code+=bytes.fromhex('0702540c02000e000000')
   run(f'iter-slot{slot}-mode{mode}-rcp{dep}',code)
