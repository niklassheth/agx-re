#!/usr/bin/env python3
"""Copy a whole captured twelve-varying vertex launcher, without decoding it.

The fragment half remains the EXP-M4-58 four-buffer launcher. This writes
external runtime data, never C arrays or production compiler instruction code.
Only load trusted captures: pickle is not an untrusted-data format.
"""
import argparse
import gzip
import hashlib
import pickle
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('capture', type=Path)
p.add_argument('four_buffer_launch', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
old = a.four_buffer_launch.read_bytes()
assert len(old) == 0x180
with gzip.open(a.capture, 'rb') as f:
    capture = pickle.load(f)
address = 0x10000220000
launch = next(m['data'][address-m['va']:address-m['va']+0xc0]
              for m in capture['client_mappings']
              if m['va'] <= address and address + 0xc0 <= m['va'] + len(m['data']))
result = launch + old[0xc0:]
a.output.write_bytes(result)
print(hashlib.sha256(result).hexdigest())
