#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain opaque native preloads and data records from our recorded API probe.

This is a capture-specific research tool. It does not decode executable bytes
or copy either API shader main. Only known binding pointers and entry selectors
are patched by the separate Mesa compatibility packager.
"""
import argparse
import gzip
import hashlib
import pickle
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
source = Path(__file__).resolve().parent / 'native.pkl.gz'
assert hashlib.sha256(source.read_bytes()).hexdigest() == (
    'd45f048a51379de1c27dfaf1f685a2dc43b28bf64eebdcbab5539faac07bbeaf')
capture = pickle.load(gzip.open(source, 'rb'))
pages = {m['va']: m['data'] for m in capture['client_mappings']}

def span(relative, size):
    address = 0x10000000000 + relative
    page = address & ~0x3fff
    assert address + size <= page + 0x4000
    return pages[page][address - page:address - page + size]

blob = (span(0x220000, 0xc0) + span(0x230640, 0xc0) +
        span(0x400a0, 0x40) + span(0x40020, 0x40))
assert len(blob) == 0x200
args.output.write_bytes(blob)
print(hashlib.sha256(blob).hexdigest(), args.output)
