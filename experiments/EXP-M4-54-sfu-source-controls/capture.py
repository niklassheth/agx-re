#!/usr/bin/env python3
"""Capture only our own Metal kernels; retain raw mains and compile logs."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('agxparse', HERE/'tools/agxparse.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
source = HERE/'source_controls.metal'
out = HERE/'native'
out.mkdir(exist_ok=True)
records = []
for name in re.findall(r'kernel void (\w+)\(', source.read_text()):
    archive = out/f'{name}.bin'
    proc = subprocess.run([str(HERE/'tools/shdump'), '-o', str(archive),
                           '-f', name, str(source)], capture_output=True,
                          text=True, timeout=45)
    (out/f'{name}.log').write_text(proc.stdout+proc.stderr)
    if proc.returncode:
        raise RuntimeError(f'compile failed: {name}: {proc.stderr}')
    _, pieces = parser.extract_agx(archive.read_bytes())
    main = pieces['_agc.main']
    (out/f'{name}.main.hex').write_text(main.hex()+'\n')
    # Small matched shaders: retain candidates for full local length validation.
    candidates = [dict(offset=i, hex=main[i:i+10].hex())
                  for i in range(0, len(main)-9, 2)
                  if main[i] in (0x2f, 0xaf) and main[i+2]&0xfc == 0x54]
    record = dict(name=name, length=len(main), candidates=candidates)
    records.append(record)
    print(json.dumps(record), flush=True)
(HERE/'NATIVE.json').write_text(json.dumps(records, indent=2)+'\n')
