#!/usr/bin/env python3
"""Raw SFU field census, restricted to public/own-source shader mains."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

parser = module('agxparse', ROOT/'experiments/EXP-0030-mesh/harness/agxparse.py')
isa = module('isadb', ROOT/'tools/agx-isa/isadb.py')
corpus = ROOT/'experiments/EXP-M4-32-public-metal-corpus/captures'
seen = set()
counts = collections.Counter()
examples = collections.defaultdict(list)
records = []
stats = collections.Counter()
for path in sorted(corpus.rglob('*.bin')):
    stats['archives'] += 1
    try:
        _, parts = parser.extract_agx(path.read_bytes())
        main = parts.get('_agc.main', b'') if parts else b''
    except Exception:
        stats['extraction_failures'] += 1
        continue
    if not main:
        stats['empty_main'] += 1
        continue
    digest = hashlib.sha256(main).hexdigest()
    if digest in seen:
        continue
    seen.add(digest)
    stats['unique_mains'] += 1
    off = 0
    while off < len(main):
        length = isa.instr_length(main, off)
        if not length or off+length > len(main):
            stats['partial_walks'] += 1
            break
        raw = main[off:off+length]
        if length == 10 and raw[0] in (0x2f, 0xaf):
            # Do not filter on the suspect byte-6 opcode/lifetime labels.
            key = f'{raw[0]:02x}:{raw[1]&15:x}:{raw[6]:02x}:{raw[7]:02x}:{raw[8]:02x}:{raw[9]:02x}'
            counts[key] += 1
            rec = dict(archive=str(path.relative_to(corpus)), sha256=digest,
                       offset=off, hex=raw.hex(), key=key)
            records.append(rec)
            if len(examples[key]) < 4:
                examples[key].append(rec)
        off += length
    stats['walked_bytes'] += off
    stats['main_bytes'] += len(main)
result = dict(stats=stats, counts=dict(counts.most_common()), examples=examples,
              records=records)
(HERE/'CORPUS.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(stats=stats, counts=dict(counts.most_common())), indent=2))
