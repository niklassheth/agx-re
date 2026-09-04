#!/usr/bin/env python3
"""Measure isolated own-source SFUs and native controls, retaining raw bits."""
import importlib.util
import json
from pathlib import Path
import random
import struct
import subprocess

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('agxparse', HERE/'tools/agxparse.py')
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)
WORK = HERE/'raw'
WORK.mkdir(exist_ok=True)
records = []

def bits(x):
    return struct.unpack('<I', struct.pack('<f', x))[0]

def execute(name, tag, words, instruction=None):
    blob = bytearray((HERE/'native'/f'{name}.bin').read_bytes())
    base, size = parser.locate_region(blob, '_agc.main')
    if instruction:
        assert name in ('k_rsqrt', 'k_sqrt')
        assert blob[base+18] in (0xaf, 0x2f) and blob[base+19:base+21] == bytes.fromhex('0156')
        blob[base+18:base+28] = bytes.fromhex(instruction)
    ident = name+'__'+tag
    archive = WORK/f'{ident}.bin'
    archive.write_bytes(blob)
    (WORK/'input.bin').write_bytes(struct.pack('<'+'I'*len(words), *words))
    cmd = [str(HERE/'tools/agxrun'), '--archive', str(archive),
           '--source', str(HERE/'assist.metal'), '--function', name,
           '--grid', str(len(words)), '--tg', '32',
           '--buf', '0='+str(WORK/'input.bin'), '--out', f'1={4*len(words)}']
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    (WORK/f'{ident}.log').write_text(p.stdout+p.stderr)
    if p.returncode or 'STATUS OK' not in p.stdout:
        raise RuntimeError(f'{ident}: {p.stdout} {p.stderr}')
    raw = next(l.split()[2] for l in p.stdout.splitlines() if l.startswith('OUT 1 '))
    output = list(struct.unpack('<'+'I'*len(words), bytes.fromhex(raw)))
    rec = dict(name=name, tag=tag, instruction=instruction,
               inputs=[f'{w:08x}' for w in words], outputs=[f'{w:08x}' for w in output])
    records.append(rec)
    (HERE/'HARDWARE.json').write_text(json.dumps(records, indent=2)+'\n')
    preview = [struct.unpack('<f', struct.pack('<I', w))[0] for w in output[:32]]
    print(json.dumps(dict(name=name, tag=tag, count=len(words), preview=preview)), flush=True)

def main():
    edges = [0,0x80000000,0x7f800000,0xff800000,0x7fc00000,0x7f800001,
             1,0x007fffff,0x00800000,0x80000001,0x807fffff,0x80800000,
             bits(0.125),bits(0.25),bits(0.5),bits(1),bits(2),bits(4),bits(9),bits(16),
             bits(-0.125),bits(-0.25),bits(-0.5),bits(-1),bits(-2),bits(-4),
             0x3f7fffff,0x3f800001,0xbf7fffff,0xbf800001,0x7f7fffff,0xff7fffff]
    for name in ['k_rsqrt','k_sqrt','k_sqrt_precise','k_sin','k_sin_fast','k_sinpi','k_cospi']:
        execute(name, 'native_edges', edges)
    for family in [0xaf,0x2f]:
        for ctl in [0x90,0x92,0xb0,0xb2]:
            ins = bytes([family,1,0x56,0,2,0,ctl,0x40,0,0]).hex()
            execute('k_rsqrt', f'root_{family:02x}_{ctl:02x}', edges, ins)
    for family in [0x2f,0xaf]:
        ins = bytes([family,3,0x56,0,2,0,0xb0,0x40,0,0]).hex()
        execute('k_rsqrt', f'class3_{family:02x}_edges', edges, ins)

    dense = [bits((i-2048)/2048) for i in range(4096)]
    execute('k_rsqrt', 'class3_dense', dense, '2f0356000200b0400000')
    rng = random.Random(55)
    random_words = [rng.getrandbits(32) for _ in range(4096)]
    execute('k_rsqrt', 'class3_random', random_words, '2f0356000200b0400000')
    positive = [rng.randrange(0x00800000,0x7f800000) for _ in range(4096)]
    for family in [0xaf,0x2f]:
        execute('k_rsqrt', f'root_{family:02x}_random', positive,
                bytes([family,1,0x56,0,2,0,0xb0,0x40,0,0]).hex())
    execute('k_sqrt', 'native_random', positive)

if __name__ == '__main__':
    main()
