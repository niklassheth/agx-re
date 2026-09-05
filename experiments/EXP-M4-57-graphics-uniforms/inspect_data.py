# SPDX-License-Identifier: MIT
# Locate authored data and pointers only; never decode opaque executable code.
import gzip, pickle, struct
from pathlib import Path
p=Path(__file__).resolve().parent
a=pickle.load(gzip.open(p/'native.pkl.gz','rb'))
maps=a['client_mappings']
for name,values in [('vertex',[1,0,0,1,0,1,0,1,0,0,1,1]),('fragment',[.5,.5,.5,1,.75,.75,.75,1])]:
 needle=struct.pack('<'+'f'*len(values),*values)
 targets=[]
 for m in maps:
  data=m['data']; off=data.find(needle)
  if off>=0:
   address=m['va']+off; targets.append(address); print(name,'data',hex(address))
 for address in targets:
  needle=struct.pack('<Q',address)
  for m in maps:
   data=m['data']; off=data.find(needle)
   while off>=0:
    print(name,'pointer',hex(m['va']+off),'context',data[max(0,off-16):off+24].hex())
    off=data.find(needle,off+8)
for label, target in [('VS',0x2000c0),('FS',0x348600)]:
 for m in maps:
  if not 0x10000000000 <= m['va'] < 0x10000400000: continue
  b=m['data']
  for i in range(len(b)-8):
   if b[i+1]&0x80 and (b[i+1]&0x7f)|((b[i+4]&0x1e)<<6)|((b[i+5]&12)<<9)|(int.from_bytes(b[i+6:i+8],'little')<<13)==target:
    print(label,'compact reference',hex(m['va']+i),b[i:i+16].hex())
