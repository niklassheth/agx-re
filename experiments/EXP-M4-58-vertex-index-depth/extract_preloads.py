#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract opaque four-buffer launch records from our pinned Metal capture.

No executable decoding. API shader mains are outside these launch records.
The compatibility packager changes only the pointer-table reference and the
existing archive-call selector; the rest of each record remains opaque.
"""
import argparse,gzip,hashlib,pickle
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);args=p.parse_args()
source=Path(__file__).resolve().parent/'native.pkl.gz'
assert hashlib.sha256(source.read_bytes()).hexdigest()=='c40db3241ebdf3bf9b4f9f25d7f868ac4cceb2c5e96434e94fe2cf70896afd31'
cap=pickle.load(gzip.open(source,'rb'));maps={m['va']:m['data'] for m in cap['client_mappings']}
def span(relative,size):
 address=0x10000000000+relative;page=address&~0x3fff;offset=address-page
 assert offset+size<=0x4000
 return maps[page][offset:offset+size]
blob=span(0x220000,0xc0)+span(0x230640,0xc0)
args.output.write_bytes(blob)
print(hashlib.sha256(blob).hexdigest(),args.output)
