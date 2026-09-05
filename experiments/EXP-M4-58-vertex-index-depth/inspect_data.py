# SPDX-License-Identifier: MIT
# Authored input bytes and command/data pointers only. No executable decoding.
import gzip,pickle,struct
from pathlib import Path
p=Path(__file__).resolve().parent
cap=pickle.load(gzip.open(p/'native.pkl.gz','rb'))
maps=cap['client_mappings']
print('keys',cap.keys())
for stage in range(2):
 for slot in range(4):
  values=[.03125*(1+stage*32+slot*4+i%4) for i in range(12)]
  if stage==slot==0: values=[-.75,-.75,.25,1,.75,-.75,.25,1,0,.75,.25,1]
  needle=struct.pack('<12f',*values)
  for m in maps:
   off=m['data'].find(needle)
   if off<0: continue
   address=m['va']+off
   print('data',stage,slot,hex(address))
   ptr=struct.pack('<Q',address)
   for n in maps:
    i=n['data'].find(ptr)
    if i>=0: print(' table',hex(n['va']+i),n['data'][i:i+32].hex())
# Command stream data: VDM words; PPP state group.
for m in maps:
 if m['va'] in (0x10000018000,0x10000058000):
  print('commands',hex(m['va']))
  for i in range(0,0xa0,16): print(hex(i),[hex(x) for x in struct.unpack_from('<4I',m['data'],i)])
for target in [0x200160,0x348600]:
 for m in maps:
  if not 0x10000000000 <= m['va'] < 0x10000400000: continue
  b=m['data']
  for i in range(len(b)-8):
   ptr=(b[i+1]&0x7f)|((b[i+4]&0x1e)<<6)|((b[i+5]&12)<<9)|(int.from_bytes(b[i+6:i+8],'little')<<13)
   if b[i+1]&0x80 and ptr==target:
    print('compact table reference',hex(target),hex(m['va']+i),b[i:i+16].hex())
for m in maps:
 for needle in [bytes.fromhex('2e000040'), bytes.fromhex('0006f261')]:
  i=m['data'].find(needle)
  if i>=0:
   print('command pattern',hex(m['va']+i),m['data'][max(0,i-12):i+48].hex())
print('queues',[(q.keys()) for q in cap['queues'].values()] if isinstance(cap['queues'],dict) else 'list')
