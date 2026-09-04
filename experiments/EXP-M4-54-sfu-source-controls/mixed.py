#!/usr/bin/env python3
"""Native narrow-source/wide-result controls, without mutation."""
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('agxparse', HERE/'tools/agxparse.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
source = HERE/'mixed.metal'
out = HERE/'mixed'
out.mkdir(exist_ok=True)
values = [0.5, 1., 2., 4., 0.25, 8., 3., 1.5]
records = []
for name in re.findall(r'kernel void (\w+)\(', source.read_text()):
    archive = out/f'{name}.bin'
    proc = subprocess.run([str(HERE/'tools/shdump'), '-o', str(archive),
                           '-f', name, str(source)], capture_output=True,
                          text=True, timeout=45)
    (out/f'{name}.compile.log').write_text(proc.stdout+proc.stderr)
    if proc.returncode:
        raise RuntimeError(proc.stderr)
    _, pieces = parser.extract_agx(archive.read_bytes())
    main = pieces['_agc.main']
    (out/f'{name}.main.hex').write_text(main.hex()+'\n')
    candidates = [dict(offset=i, hex=main[i:i+10].hex())
                  for i in range(0, len(main)-9, 2)
                  if main[i] in (0x2f, 0xaf) and main[i+2]&0xfc == 0x54]
    if '_half_' in name:
        data = struct.pack('<8e', *values)
    else:
        data = b''.join(struct.pack('<f', x)[2:] for x in values)
    (out/'input.bin').write_bytes(data)
    (out/'bias.bin').write_bytes(struct.pack('<8f', *([0.25]*8)))
    proc = subprocess.run([str(HERE/'tools/agxrun'), '--source', str(source),
        '--archive', str(archive), '--function', name, '--grid', '8', '--tg', '8',
        '--buf', '0='+str(out/'input.bin'), '--buf', '1='+str(out/'bias.bin'),
        '--out', '2=32', '--out', '3=32'], capture_output=True, text=True, timeout=30)
    (out/f'{name}.run.log').write_text(proc.stdout+proc.stderr)
    if proc.returncode or 'STATUS OK' not in proc.stdout:
        raise RuntimeError(proc.stdout+proc.stderr)
    outputs = {}
    for line in proc.stdout.splitlines():
        if line.startswith('OUT '):
            _, index, raw = line.split()
            outputs[index] = list(struct.unpack('<8f', bytes.fromhex(raw)))
    rec = dict(name=name, candidates=candidates, outputs=outputs)
    records.append(rec)
    print(json.dumps(rec), flush=True)
    (HERE/'MIXED.json').write_text(json.dumps(records, indent=2)+'\n')
