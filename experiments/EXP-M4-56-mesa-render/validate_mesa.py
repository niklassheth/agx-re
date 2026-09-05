"""Independent raster/color oracle; only caller shader mains are replaced."""
import json,re,subprocess
from pathlib import Path
import agxparse
blob=Path('large.bin').read_bytes();results=[]
for vs,fs in [('vertex','fragment'),('vertex-w','fragment'),('vertex-small','fragment'),('vertex','fragment-alt')]:
 data=bytearray(blob)
 for stage,name in [('vertex',vs),('fragment',fs)]:
  base,size=agxparse.locate_region(blob,'_agc.main',stage);body=Path('mesa-'+name+'.bin').read_bytes();assert len(body)<=size
  data[base:base+size]=body+bytes(size-len(body))
 name=f'validated-{vs}-{fs}';Path(name+'.archive').write_bytes(data)
 p=subprocess.run(['./agxrender','--archive',name+'.archive','--source','probe.metal','--vertex','v_main','--fragment','f_main','--width','64','--height','64','--no-fast-math'],capture_output=True,text=True,timeout=40)
 Path(name+'.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stdout+p.stderr
 pixels=re.findall(r'PIXEL (\d+) (\d+) bgra=([0-9a-f]{8})',p.stdout);assert len(pixels)==4096
 errors=[];covered=0;maxerr=0
 for sx,sy,word in pixels:
  x=(int(sx)+.5)/32-1;y=1-(int(sy)+.5)/32
  if vs=='vertex-small':x=(x-.125)*2;y*=2
  b=(y+.75)/1.5;g=(x+.75-.75*b)/1.5;r=1-g-b
  if min(r,g,b)>0:
   covered+=1
   if vs=='vertex-w':
    r,g,b=r,g/2,b/4;total=r+g+b;r/=total;g/=total;b/=total
   rgb=(1-r,g*g,.25+b*.5) if fs=='fragment-alt' else (r*r,g+.125,b*.5)
   expected=[round(max(0,min(1,v))*255) for v in rgb]+[255]
  else:expected=[0,0,0,0]
  raw=bytes.fromhex(word);actual=[raw[2],raw[1],raw[0],raw[3]]
  err=max(abs(a-b) for a,b in zip(actual,expected));maxerr=max(maxerr,err)
  if err>1:errors.append({'xy':[sx,sy],'actual':actual,'expected':expected})
 result={'vertex':vs,'fragment':fs,'pixels':len(pixels),'covered':covered,'max_channel_error':maxerr,'errors':errors[:10],'error_count':len(errors)}
 results.append(result);print(json.dumps(result),flush=True)
Path('VALIDATION.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['error_count']==0 for r in results)
