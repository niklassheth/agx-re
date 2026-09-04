#!/usr/bin/env python3
"""Execute native controls and isolated SFU mutations via own-source archives."""
import importlib.util
import json
import math
from pathlib import Path
import struct
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('agxparse', HERE/'tools/agxparse.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
WORK = HERE/'measurements'
WORK.mkdir(exist_ok=True)
NATIVE = {r['name']: r for r in json.loads((HERE/'NATIVE.json').read_text())}
VALUES = [0.5, 1., 2., 4., 0.25, 8., 3., 1.5]
records = []

def execute(name, tag='native', patches=None, words=None):
    op, typ, shape = name.split('_')
    fmt = 'f' if typ == 'float' else 'e'
    width = struct.calcsize(fmt)
    blob = bytearray((HERE/'native'/f'{name}.bin').read_bytes())
    base, size = parser.locate_region(blob, '_agc.main')
    candidates = NATIVE[name]['candidates']
    assert len(candidates) == 1
    off = candidates[0]['offset']
    for byte, value in (patches or {}).items():
        blob[base+off+byte] = value
    ident = name+'__'+tag
    archive = WORK/f'{ident}.bin'
    archive.write_bytes(blob)
    input_data = (struct.pack('<8I', *words) if words is not None else
                  struct.pack('<8'+fmt, *VALUES))
    (WORK/'input.bin').write_bytes(input_data)
    (WORK/'bias.bin').write_bytes(struct.pack('<8'+fmt, *([0.25]*8)))
    cmd = [str(HERE/'tools/agxrun'), '--archive', str(archive),
           '--source', str(HERE/'source_controls.metal'), '--function', name,
           '--grid', '8', '--tg', '8', '--buf', '0='+str(WORK/'input.bin'),
           '--buf', '1='+str(WORK/'bias.bin'), '--out', f'2={8*width}',
           '--out', f'3={8*width}']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    (WORK/f'{ident}.log').write_text(result.stdout+result.stderr)
    if result.returncode or 'STATUS OK' not in result.stdout:
        raise RuntimeError(f'{ident}: {result.stdout} {result.stderr}')
    outputs = {}
    raw_outputs = {}
    for line in result.stdout.splitlines():
        if line.startswith('OUT '):
            _, index, raw = line.split()
            raw_outputs[index] = raw
            outputs[index] = list(struct.unpack('<8'+fmt, bytes.fromhex(raw)))
    rec = dict(name=name, tag=tag, instruction=blob[base+off:base+off+10].hex(),
               input_hex=input_data.hex(), outputs=outputs, raw_outputs=raw_outputs)
    records.append(rec)
    (HERE/'HARDWARE.json').write_text(json.dumps(records, indent=2)+'\n')
    print(json.dumps(rec), flush=True)

for name in NATIVE:
    execute(name)

for op in ['rcp', 'rsqrt', 'exp2', 'log2', 'floor']:
    release = 0x10 if op == 'rcp' else 0xb0
    execute(op+'_float_reuse', 'forced_release', {6: release})
    if op != 'rcp':
        # Distinguish FP32 from packed FP16/BF16, and both 16-bit halves.
        words = [0x40003c00, 0x42004000, 0x44004400, 0x45004800,
                 0x46003800, 0x47003400, 0x48004200, 0x49003e00]
        execute(op+'_float_store', 'a0_packed_half', {6: 0xa0}, words)
        execute(op+'_float_store', 'b0_packed_half_control', words=words)
        execute(op+'_half_reuse', 'forced_release', {6: 0xac})
    else:
        execute(op+'_half_reuse', 'forced_release', {6: 0x10})
        execute(op+'_float_reuse', 'b6_02', {6: 0x02})
        execute(op+'_float_reuse', 'b6_12', {6: 0x12})

# Sign/absolute evidence with mixed signed inputs, independent from builtins.
signed = [0x3f000000, 0xbf000000, 0x40000000, 0xc0000000,
          0x40800000, 0xc0800000, 0x3fc0000, 0xbfc00000]
for op in ['exp2', 'floor', 'rsqrt', 'log2']:
    execute(op+'_float_store', 'negate_input', {8: 3 if op == 'floor' else 1}, signed)
    execute(op+'_float_store', 'absolute_input', {7: 0xc0}, signed)
