#!/usr/bin/env python3
"""Independent arithmetic and source-lifetime oracles; NaNs explicit."""
import json
import math
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent

def rounded(x, fmt):
    try:
        return struct.unpack('<'+fmt, struct.pack('<'+fmt, x))[0]
    except OverflowError:
        return math.copysign(math.inf, x)

def function(op, x):
    if op == 'rcp':
        return 1/x if x else math.copysign(math.inf, x)
    if op == 'rsqrt':
        return math.nan if x < 0 else 1/math.sqrt(x) if x else math.copysign(math.inf, x)
    if op == 'log2':
        return math.nan if x < 0 else math.log2(x) if x else -math.inf
    if op == 'exp2':
        return 2**x if x < 1024 else math.inf
    if op == 'floor':
        return math.copysign(0, x) if x == 0 else float(math.floor(x))
    raise ValueError(op)

def matches(got, expected, fmt, tolerance):
    expected = rounded(expected, fmt)
    if math.isnan(expected):
        return math.isnan(got)
    if math.isnan(got):
        return False
    a, b = struct.pack('<'+fmt, got), struct.pack('<'+fmt, expected)
    if not math.isfinite(expected) or expected == 0:
        return a == b
    if not math.isfinite(got) or math.copysign(1, got) != math.copysign(1, expected):
        return False
    return abs(int.from_bytes(a, 'little') - int.from_bytes(b, 'little')) <= tolerance

failures = []
checks = 0
records = json.loads((HERE/'HARDWARE.json').read_text())
for rec in records:
    op, typ, shape = rec['name'].split('_')
    fmt = 'f' if typ == 'float' else 'e'
    raw = bytes.fromhex(rec['input_hex'])
    values = list(struct.unpack('<8'+fmt, raw))
    if rec['tag'] == 'a0_packed_half':
        # Prediction after model discovery: LOW bfloat16, not IEEE half or high16.
        words = struct.unpack('<8I', raw)
        values = [struct.unpack('<f', struct.pack('<I', (x & 65535)<<16))[0]
                  for x in words]
    for i, x in enumerate(values):
        if shape == 'alu':
            x = rounded(x+0.25, fmt)
        if shape == 'neg' or rec['tag'] == 'negate_input':
            x = -x
        if shape == 'abs' or rec['tag'] == 'absolute_input':
            x = abs(x)
        expected = function(op, x)
        saved = rounded(x+0.25, fmt) if shape == 'reuse' else 0.25
        if rec['tag'] in ['forced_release', 'b6_12']:
            saved = 0.25
        for index, value, tolerance in [('2', expected, 0 if op == 'floor' else 2),
                                         ('3', saved, 0)]:
            checks += 1
            if not matches(rec['outputs'][index][i], value, fmt, tolerance):
                failures.append(dict(name=rec['name'], tag=rec['tag'], lane=i,
                                     output=index, got=rec['outputs'][index][i],
                                     expected=value))

mixed = json.loads((HERE/'MIXED.json').read_text()) if (HERE/'MIXED.json').exists() else []
for rec in mixed:
    op, _, shape = rec['name'].split('_')
    for i, x in enumerate([0.5, 1., 2., 4., 0.25, 8., 3., 1.5]):
        for index, expected, tolerance in [('2', function(op, x), 0 if op == 'floor' else 2),
                ('3', x+0.25 if shape == 'reuse' else 0.25, 0)]:
            checks += 1
            if not matches(rec['outputs'][index][i], expected, 'f', tolerance):
                failures.append(dict(name=rec['name'], lane=i, output=index,
                                     got=rec['outputs'][index][i], expected=expected))
result = dict(cases=len(records)+len(mixed), checks=checks, failures=failures,
              verdict='PASS' if not failures else 'FAIL')
(HERE/'VERIFICATION.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
raise SystemExit(bool(failures))
